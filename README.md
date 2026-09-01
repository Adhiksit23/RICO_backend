#  Setup & Run Guide

## Project Structure


UI/
├── backend/
└── frontend/

---

# Backend Setup (FastAPI)

## 1. Open Terminal

Go to backend folder:

cd UI/backend

---

## 2. Create Virtual Environment

python -m venv venv

---

## 3. Activate Virtual Environment


.\venv\Scripts\activate

from macOS / Linux

source venv/bin/activate 

You should now see:

(venv)

---

## 4. Install Dependencies

pip install -r requirements.txt

---

## 5. Run Backend Server


python -m uvicorn main:app --reload

Backend will run on:

http://127.0.0.1:8000

Swagger Docs:
 #You can see the backend connected to run exactly do this 

http://127.0.0.1:8000/docs

---

# Frontend Setup (Next.js)

## 1. Open New Terminal

Go to frontend folder:

cd UI/frontend

---

## 2. Install Dependencies

npm install

---

## 3. Run Frontend

npm run dev

Frontend will run on:

http://localhost:3000

---

# Available Frontend Routes

/dashboard
/monitor
/calibration
/settings

Example:

http://localhost:3000/calibration

---

# Calibration APIs

## Existing Summary API


/api/calibrator/run


Used for:

* Samples analyzed
* Avg CPK
* Excellent parameters

---

##  Calibration Workflow APIs

### Fetch latest parameters


/api/calibration/latest


### Fetch calibration ranges


/api/calibration/ranges


### Update parameters


/api/calibration/update


### Apply calibration


/api/calibration/apply


# Important Notes

* Start backend BEFORE frontend.
* Backend must run on port 8000.
* Frontend expects backend APIs from:


http://127.0.0.1:8000


* Do NOT upload:


venv/
node_modules/
.next/


* Use `requirements.txt` for backend dependency setup.
