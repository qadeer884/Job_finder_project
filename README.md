# Job Finder API

A Job Finder API built for a Machine Learning Engineer assessment at GoAccelovate.  
This RESTful API fetches job listings from various platforms, uses an AI model to analyze job descriptions, and delivers structured, personalized job recommendations.

## 🚀 Project Objective

To develop a system that:
- Scrapes job listings from platforms like LinkedIn, Indeed, Glassdoor, and Google Jobs.
- Uses a Large Language Model (LLM) to extract experience requirements, skills, and job-candidate interest matches.
- Provides a clean, structured JSON response through a FastAPI backend.

## 🛠️ Technology Stack

- **FastAPI** — for API services  
- **Python** — core backend  
- **jobspy** — job scraping  
- **LangChain + Groq LLaMA** — LLM-powered job description analysis  
- **Pandas** — data manipulation  
- **HTML/CSS** — simple frontend  
- **Railway** — for deployment  

## 🔍 System Workflow

1. User submits job search criteria via JSON or a web form.
2. jobspy scrapes jobs based on selected platform(s).
3. Each job description is analyzed using an LLM.
4. API returns structured JSON with:
   - Required Experience  
   - Skills List  
   - Interest Match  

5. Optionally view/search jobs via a basic frontend.

## 🎥 Demo Video

[Watch Here](https://drive.google.com/file/d/1d1PkYSTr6zCbuyCnTIVJGRxBQIRLnMDS/view?usp=drive_link)

## 🌐 Live API

[Job Finder API (Deployed on Railway)](https://jobfinder.up.railway.app)

