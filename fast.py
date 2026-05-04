import csv
import pandas as pd
import json
import logging
from jobspy import scrape_jobs
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
from pydantic import BaseModel
import dotenv
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()

# Groq API config
key = os.getenv("GROQ_API_KEY")

model = ChatGroq(
    model="llama3-70b-8192",
    temperature=0.5,
    max_tokens=None,
    timeout=None,
    max_retries=3,
    api_key=key
)

# Updated Prompt Template
messages = [
    (
        "system",
        "You are an expert assistant for job seekers and HR professionals. "
        "Analyze each job description to extract structured details and also determine if it matches the user's interests "
        "(role, required skills, and job nature)."
    ),
    (
        "human",
        """Given the following job description:

{job}

And the user's input:

{user_input}

Extract and return a JSON object with these fields:

{{
    "Experience": "<number of years mentioned in the job description or 'not specified'>",
    "Skills": ["<list of skills mentioned in the job description or 'not specified'>"],
    "Interest": "<'yes' if the user's interests align with the position, skills, and nature; otherwise 'no'>"
}}

Return only the JSON (no additional text, spaces, or anything else)."""
    ),
]

prompt_template = ChatPromptTemplate.from_messages(messages)
chain = prompt_template | model | StrOutputParser()

# Scraping logic
def scrape_with_country_logic(
    search_term: str,
    results_wanted: int,
    hours_old: int,
    site_name: str,
    c_name: str
) -> pd.DataFrame:
    logger.info(f"Scraping jobs for {search_term} on {site_name} in {c_name}")
    if site_name.lower() == "glassdoor" and c_name.lower() == "pakistan":
        country_indeed = "USA"
    else:
        country_indeed = c_name

    common_kwargs = {
        'search_term': search_term,
        'google_search_term': f"{search_term} jobs in {country_indeed}",
        'location': c_name,
        'results_wanted': results_wanted,
        'hours_old': hours_old,
        'linkedin_fetch_description': True
    }

    jobs_frames = []
    try:
        jobs = scrape_jobs(
            site_name=[site_name.lower()],
            country_indeed=country_indeed,
            **common_kwargs
        )
        if jobs is not None and not jobs.empty:
            logger.info(f"Scraped {len(jobs)} jobs from {site_name}")
            jobs_frames.append(jobs)
        else:
            logger.warning(f"No jobs scraped from {site_name}")
    except Exception as e:
        logger.error(f"Error scraping jobs for {site_name} in {country_indeed}: {str(e)}")
        return pd.DataFrame()

    if not jobs_frames:
        logger.warning("No job frames collected")
        return pd.DataFrame()
    combined_jobs = pd.concat(jobs_frames, ignore_index=True)
    return combined_jobs

# Main job processing function
def process_job_search(user_input: dict) -> list:
    logger.info(f"Processing job search with input: {user_input}")
    
    # Extract parameters from user_input
    source = user_input['source']
    jobPosition = user_input['jobPosition']
    location = user_input['location']
    jobAge = user_input['jobAge']
    
    site_mapping = {
        "LinkedIn": "linkedin",
        "Indeed": "indeed",
        "Google Jobs": "google",
        "Glassdoor": "glassdoor"
    }
    site_name = site_mapping.get(source, "indeed")
    
    search_term = jobPosition
    c_name = location
    try:
        hours_old = int(jobAge) * 24
    except ValueError:
        logger.error(f"Invalid jobAge value: {jobAge}")
        raise HTTPException(status_code=400, detail="jobAge must be a valid number")
    results_wanted = 20

    # Scrape jobs
    jobs_df = scrape_with_country_logic(
        search_term=search_term,
        results_wanted=results_wanted,
        hours_old=hours_old,
        site_name=site_name,
        c_name=c_name
    )

    if jobs_df.empty:
        logger.warning("No jobs scraped, returning empty list")
        return []

    # Enrich jobs with LLM
    experiences, skills_list, interests = [], [], []
    for idx, row in jobs_df.iterrows():
        desc = str(row.get('description', 'Not Available'))
        if desc.strip() and desc != 'Not Available':
            user_input_str = json.dumps(user_input, indent=4)
            try:
                result_json = chain.invoke({"job": desc, "user_input": user_input_str}).strip()
                result_dict = json.loads(result_json)
                experiences.append(result_dict.get('Experience', 'not specified'))
                skills_list.append(', '.join(result_dict.get('Skills', ['not specified'])))
                interests.append(result_dict.get('Interest', 'no'))
            except json.JSONDecodeError as e:
                logger.error(f"LLM JSON parsing failed for job {idx}: {str(e)}")
                experiences.append('not specified')
                skills_list.append('not specified')
                interests.append('no')
            except Exception as e:
                logger.error(f"LLM processing failed for job {idx}: {str(e)}")
                experiences.append('not specified')
                skills_list.append('not specified')
                interests.append('no')
        else:
            experiences.append('not specified')
            skills_list.append('not specified')
            interests.append('no')

    jobs_df['Experience'] = experiences
    jobs_df['Skills'] = skills_list
    jobs_df['Interest'] = interests

    # Calculate salaries
    def calculate_salary(row):
        try:
            interval = str(row.get('interval', '')).lower()
            max_amount = float(row.get('max_amount', 0) or 0)
            if interval == 'monthly' and max_amount > 0:
                return max_amount * 12
            return max_amount if max_amount > 0 else 'Not Specified'
        except:
            return 'Not Specified'

    jobs_df['Salary'] = jobs_df.apply(calculate_salary, axis=1)
    jobs_df['Job nature'] = jobs_df.get('is_remote').map({True: 'Remote', False: 'On-site'}, na_action='ignore').fillna('On-site')

    # Prepare final DataFrame
    jobs_df['Source'] = source
    jobs_df['Job title'] = jobs_df['title']
    jobs_df['Company'] = jobs_df['company']
    jobs_df['Location'] = jobs_df['location']
    jobs_df['Date of Posted'] = jobs_df['date_posted']
    jobs_df['Apply_link'] = jobs_df['job_url']
    jobs_df['Job Description'] = jobs_df['description'].fillna('Not Available')

    final_columns = [
        'Source', 'Job title', 'Company', 'Experience', 'Job nature', 'Location', 'Salary',
        'Date of Posted', 'Apply_link', 'Job Description', 'Skills', 'Interest'
    ]
    final_df = jobs_df[final_columns]

    # Fix for nan values
    final_df = final_df.fillna('Not Specified')

    logger.info(f"Returning {len(final_df)} jobs")
    return final_df.to_dict(orient='records')

# FastAPI app
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:5000", "http://127.0.0.1:5000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/", response_class=FileResponse)
async def serve_index():
    logger.info("Serving index.html")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

# Updated Request schema
class JobSearchRequest(BaseModel):
    source: str
    jobPosition: str
    experience: str
    salary: str
    jobNature: str
    location: str
    skills: str
    jobAge: str

    class Config:
        extra = "ignore"

@app.post("/api/search-jobs")
async def search_jobs(request: JobSearchRequest):
    logger.info(f"Received job search request: {request.dict()}")
    try:
        jobs = process_job_search(request.dict())
        logger.info(f"Returning {len(jobs)} jobs in response")
        return jobs
    except Exception as e:
        logger.error(f"Error processing job search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)