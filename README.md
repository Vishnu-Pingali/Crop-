# 🌾 Crop Prediction Chatbot

A Django-based intelligent web application that recommends the best crop to grow based on soil and environmental parameters, powered by a **Random Forest** machine learning model and a **Telugu-language voice chatbot**.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Project Structure](#project-structure)
- [Technology Stack](#technology-stack)
- [Database Schema](#database-schema)
- [Application Modules](#application-modules)
  - [User Module](#user-module)
  - [Admin Module](#admin-module)
  - [ML & Prediction Module](#ml--prediction-module)
  - [Voice Chatbot Module](#voice-chatbot-module)
- [URL Routes](#url-routes)
- [Installation & Setup](#installation--setup)
- [How to Run](#how-to-run)
- [Usage Guide](#usage-guide)
- [Model Details](#model-details)
- [Voice Bot Details](#voice-bot-details)

---

## 📌 Overview

The **Crop Prediction Chatbot** is a full-stack Django web application designed to assist farmers and agricultural workers in making data-driven crop selection decisions. Users can either fill in a form with soil parameters or use the **Telugu-language voice chatbot** to speak their inputs and receive real-time crop recommendations.

The system uses a **Random Forest Classifier** trained on the `Crop_recommendation.csv` dataset with features such as soil nitrogen (N), phosphorus (P), potassium (K), temperature, humidity, pH, and rainfall.

---

## ✨ Features

| Feature | Description |
|---|---|
| **User Registration** | OTP-based email verification during signup |
| **Admin Approval** | New users remain in "waiting" status until an admin activates them |
| **Crop Prediction Form** | Input soil parameters via web form to get crop recommendation |
| **Voice Chatbot** | Telugu language voice input using Google Speech Recognition |
| **Model Training UI** | Train the Random Forest model in-browser with EDA visualizations |
| **Dataset Viewer** | Paginated display of the training dataset |
| **Admin Dashboard** | Full user management — activate, block, unblock, delete users |
| **Email OTP** | Secure registration via time-limited 6-digit OTP sent to user's email |

---

## 📁 Project Structure

```
crop_predication_chatbot/
│
├── manage.py                          # Django management entry point
├── requirment.txt                     # Python dependencies
├── Flow of Execution.txt              # Quick-start guide
├── crop_model.pkl                     # Pre-trained RandomForest model (pickle)
├── db.sqlite3                         # SQLite database
│
├── crop_predication_chatbot/          # Django project settings
│   ├── settings.py                    # Project configuration
│   ├── urls.py                        # Root URL configuration
│   ├── asgi.py
│   └── wsgi.py
│
├── home/                              # Main user-facing Django app
│   ├── models.py                      # userProfile model
│   ├── views.py                       # All user views (auth, prediction, chatbot)
│   ├── forms.py                       # UserProfileForm with validation
│   ├── chat1.py                       # Telugu voice chatbot engine
│   ├── admin.py
│   └── migrations/
│
├── admins/                            # Admin management Django app
│   ├── views.py                       # Admin views (login, user management)
│   └── migrations/
│
├── templates/                         # HTML Templates
│   ├── base.html                      # Base landing page
│   ├── registration.html              # User signup form
│   ├── userlogin.html                 # User login page
│   ├── adminlogin.html                # Admin login page
│   ├── verify_otp.html                # OTP verification page
│   ├── users/
│   │   ├── userhome.html              # User dashboard
│   │   ├── predict_crop.html          # Crop prediction form & results
│   │   ├── results.html               # ML training results & EDA plots
│   │   ├── chat.html                  # Voice chatbot result page
│   │   └── datasetview.html           # Dataset browser
│   └── admins/
│       ├── AdminHome.html             # Admin dashboard
│       └── viewregisterusers.html     # Registered users management table
│
├── static/                            # Static files (CSS, JS, images)
└── media/                             # Uploaded files & generated plots
    ├── Crop_recommendation.csv        # Training dataset
    ├── crop_model.pkl                 # Saved trained model
    ├── profile_photos/                # User profile images
    └── eda/                           # EDA visualizations (generated at training)
```

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| **Web Framework** | Django 5.2 |
| **REST API** | Django REST Framework 3.16 |
| **Database** | SQLite (via `db.sqlite3`) |
| **Machine Learning** | scikit-learn 1.6.1 (RandomForestClassifier) |
| **Data Processing** | pandas 2.2.3, numpy 1.26.4 |
| **Visualization** | matplotlib 3.10.1, seaborn 0.13.2 |
| **Voice Input** | SpeechRecognition 3.14.2, PyAudio 0.2.14 |
| **Translation** | googletrans 4.0.0rc1 |
| **Text-to-Speech** | gTTS 2.5.4, playsound 1.2.2 |
| **Email (OTP)** | Django `send_mail` via SMTP |
| **Model Serialization** | pickle (Python standard library) |
| **Frontend** | HTML5, CSS3, Bootstrap (via base templates) |

---

## 🗄️ Database Schema

### `userProfile` (table: `home_userprofile`)

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | AutoField | Primary Key | Auto-generated ID |
| `name` | CharField(255) | Required | Full name (letters and spaces only) |
| `email` | EmailField | Unique | Used as login identifier |
| `password` | CharField(255) | Min 8 chars, 1 digit, 1 letter | Stored as plain text ⚠️ |
| `confirm_password` | CharField(255) | Must match password | Used only during registration |
| `mobile` | CharField(15) | Unique, digits only, 10-15 chars | Contact number |
| `profile_photo` | ImageField | Optional | Stored in `media/profile_photos/` |
| `status` | CharField(10) | Default: `'waiting'` | Values: `waiting`, `activated`, `blocked` |

---

## 📦 Application Modules

### User Module

**File:** `home/views.py`

| Function | URL | Description |
|---|---|---|
| `basefunction` | `/` | Renders base landing page |
| `userlogin` | `/userlogin/` | Renders user login page |
| `userregister` | `/userregister/` | Registration form with OTP trigger |
| `verify_otp` | `/verify_otp/` | OTP verification and account creation |
| `resend_otp` | `/resend_otp/` | Resend OTP (with 1-minute cooldown) |
| `userlogincheck` | `/userlogincheck/` | Authenticates user and creates session |
| `userhome` | `/userhome/<name>/` | User dashboard (login required) |
| `train_model_view` | `/train_model_view/` | Trains RandomForest and generates EDA plots |
| `predict_crop_view` | `/predict_crop_view/` | Accepts form input & returns crop prediction |
| `chatfunction` | `/chatfunction/` | Launches Telugu voice chatbot |
| `dataset_view` | `/dataset_view/` | Displays the crop recommendation dataset |

**Registration Flow:**
1. User submits registration form → OTP sent to email
2. User enters OTP → Account saved with `status='waiting'`
3. Admin activates user → User can log in

### Admin Module

**File:** `admins/views.py`

| Function | URL | Description |
|---|---|---|
| `adminlogin` | `/adminlogin/` | Admin login page |
| `AdminLoginCheck` | `/AdminLoginCheck/` | Validates admin credentials (`admin`/`admin`) |
| `adminlogout` | `/adminlogout/` | Clears admin session |
| `AdminHome` | `/AdminHome/` | Admin dashboard |
| `RegisterUsersView` | `/RegisterUsersView/` | Paginated, searchable user list |
| `activate_user` | `/activate_user/<id>/` | Sets user status to `activated` |
| `BlockUser` | `/BlockUser/<id>/` | Sets user status to `blocked` |
| `UnblockUser` | `/UnblockUser/<id>/` | Sets user status to `activated` |
| `DeleteUser` | `/DeleteUser/<id>/` | Permanently deletes user record |

> **Admin Credentials (default):** Username: `admin` | Password: `admin`

### ML & Prediction Module

**File:** `home/views.py` → `train_model_view`, `predict_crop_view`

**Training (`train_model_view`):**
- Loads `media/Crop_recommendation.csv`
- Drops nulls and duplicates (data cleaning)
- Generates per-feature **distribution histograms** and a **correlation heatmap** using seaborn
- Trains a `RandomForestClassifier(n_estimators=100, random_state=42)` on 80% of data
- Evaluates accuracy on 20% test split
- Saves model to `media/crop_model.pkl` using pickle
- Displays accuracy and all EDA plots in the browser

**Prediction (`predict_crop_view`):**
- Accepts 7 numeric inputs from POST form: N, P, K, temperature, humidity, pH, rainfall
- Loads the saved pickle model
- Returns the predicted crop label
- Returns class probability percentages for all crop types (via `predict_proba`)

**Input Features:**

| Parameter | Description | Unit |
|---|---|---|
| N | Nitrogen content in soil | mg/kg |
| P | Phosphorus content in soil | mg/kg |
| K | Potassium content in soil | mg/kg |
| temperature | Air temperature | °C |
| humidity | Relative humidity | % |
| ph | Soil pH value | 0–14 |
| rainfall | Annual rainfall | mm |

### Voice Chatbot Module

**File:** `home/chat1.py`

The voice chatbot conducts a **conversational interaction entirely in Telugu** to collect soil parameters and deliver the crop recommendation via audio output.

**Workflow:**
```
1. Greet user in Telugu (text-to-speech via gTTS)
2. Ask user "How are you?" → respond based on mood keyword
3. Ask user to say "ప్రారంభించు" (start) to begin prediction
4. Prompt for each of the 7 soil parameters via voice
5. Translate Telugu speech → English via googletrans
6. Parse numbers (float, word-to-number, or regex fallback)
7. Run model.predict() → announce recommended crop in Telugu
8. Return result dictionary to Django view → display on chat.html
```

**Key Functions:**

| Function | Description |
|---|---|
| `speak_in_telugu(text)` | Converts text to Telugu audio using gTTS and plays it |
| `get_voice_input(prompt)` | Records microphone input and recognizes Telugu speech |
| `translate_to_english(text)` | Translates Telugu text to English using googletrans |
| `get_field_value(field, prompt)` | Collects and parses a numeric value from voice input |
| `predict_crop()` | Collects all 7 inputs and runs ML prediction |
| `start_chatbot()` | Main chat loop: greeting → intent detection → prediction |

**Language:** Telugu (`te-IN` for speech recognition, `te` for gTTS)

---

## 🔗 URL Routes

```
/                          → Landing page (base.html)
/userlogin/                → User login
/userregister/             → User registration (OTP-based)
/verify_otp/               → OTP verification
/resend_otp/               → Resend OTP
/userlogincheck/           → User login credential check
/userhome/<name>/          → User dashboard
/train_model_view/         → Train ML model + EDA
/predict_crop_view/        → Crop prediction form
/chatfunction/             → Telugu voice chatbot
/dataset_view/             → View training dataset
/adminlogin/               → Admin login
/AdminLoginCheck/          → Admin credential verification
/AdminHome/                → Admin dashboard
/RegisterUsersView/        → View and manage users
/activate_user/<id>/       → Activate a user
/BlockUser/<id>/           → Block a user
/UnblockUser/<id>/         → Unblock a user
/DeleteUser/<id>/          → Delete a user
/admin/                    → Django admin panel
```

---

## ⚙️ Installation & Setup

### Prerequisites
- Python 3.9 or higher
- pip
- Windows OS (for PyAudio and playsound compatibility)
- Microphone (for voice chatbot)

### Step 1: Clone or Extract the Project
```bash
# Navigate to your project directory
cd crop_predication_chatbot
```

### Step 2: Create a Virtual Environment (Recommended)
```bash
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirment.txt
```

> **Note:** If PyAudio fails to install via pip, use pipwin:
> ```bash
> pip install pipwin
> pipwin install pyaudio
> ```

### Step 4: Configure Email (OTP System)

In `crop_predication_chatbot/settings.py`, update the email settings:
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your_email@gmail.com'
EMAIL_HOST_PASSWORD = 'your_app_password'
```

### Step 5: Apply Database Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 6: Place Dataset
Ensure `Crop_recommendation.csv` is located at:
```
media/Crop_recommendation.csv
```

---

## 🚀 How to Run

```bash
# From the project root (where manage.py is located)
python manage.py runserver
```

Open your browser and navigate to:
```
http://127.0.0.1:8000/
```

---

## 📖 Usage Guide

### For New Users:
1. Go to `http://127.0.0.1:8000/` → Click **SIGNUP**
2. Fill in name, email, password, mobile, and profile photo
3. An OTP is emailed — enter it to complete registration
4. Wait for **Admin Approval** before you can log in

### For Registered Users:
1. Click **USERLOGIN** → Enter your email and password
2. From your dashboard, you can:
   - **Train Model** — Trains the ML model and displays EDA visualizations
   - **Predict Crop** — Enter soil/weather parameters to get a crop recommendation
   - **Voice Bot** — Use Telugu voice to interact with the chatbot
   - **View Dataset** — Browse the training dataset

### For Admins:
1. Click **ADMINLOGIN** → Login with `admin` / `admin`
2. Go to **View Registered Users** to manage accounts:
   - **Activate** — Allow user to log in
   - **Block** — Prevent user from logging in
   - **Unblock** — Re-enable a blocked user
   - **Delete** — Permanently remove user record
3. Search users by name, email, or mobile number

---

## 🤖 Model Details

| Property | Value |
|---|---|
| Algorithm | Random Forest Classifier |
| Library | scikit-learn 1.6.1 |
| Estimators | 100 trees |
| Random State | 42 |
| Train/Test Split | 80% / 20% |
| Input Features | 7 (N, P, K, temperature, humidity, ph, rainfall) |
| Target | Crop label (e.g., rice, wheat, mango, etc.) |
| Model File | `media/crop_model.pkl` |
| Dataset | `media/Crop_recommendation.csv` |

**EDA Plots Generated at Training:**
- Individual feature distribution histograms (KDE overlay, 300 DPI)
- Feature correlation heatmap (coolwarm colormap)

Plots are saved to `media/eda/` and displayed in the results page.

---

## 🎙️ Voice Bot Details

| Property | Value |
|---|---|
| Language | Telugu (తెలుగు) |
| Speech Recognition | Google Speech API (`te-IN`) |
| Translation | googletrans (`te` → `en`) |
| Text-to-Speech | gTTS (`te` locale) |
| Number Parsing | float() → word2number → regex fallback |
| Threading | Runs in a background thread, result returned to Django |

**Supported voice commands:**
- `"ప్రారంభించు"`, `"start"`, `"స్టార్ట్"` — Begin crop prediction
- Mood response words: `"బాగున్నాను"`, `"happy"`, `"fine"`, `"good"`, etc.

---

## ⚠️ Known Limitations & Notes

1. **Plain-text passwords** — Passwords are stored as plain text in the database. For production use, implement Django's `make_password` / `check_password` functions.
2. **Admin credentials are hardcoded** — The default admin login (`admin` / `admin`) should be changed for production deployments.
3. **Voice chatbot requires a microphone** — The chatbot runs synchronously and blocks the thread until complete.
4. **OTP expiry logic** — OTP expiry is stored in session but not strictly enforced server-side during comparison; verify this logic during deployment.
5. **googletrans** — Uses the release candidate `4.0.0rc1`, which may have connectivity issues. Consider using a stable Google Cloud Translation API for production.

---

## 📄 License

This project is developed for academic and educational purposes.

---

*Documentation generated on March 12, 2026.*

## Security Notes

- Secrets now belong in `.env`, with `.env.example` provided for bootstrap and `.gitignore` blocking accidental commits.
- Startup configuration is environment-aware through `APP_ENV` and supports development, staging, and production behavior.
- User passwords are stored with Django hashers instead of plain text, and legacy records are migrated forward.
- REST APIs can issue and accept JWT bearer tokens, while browser flows continue to use hardened server sessions with idle expiry.
- Model training, admin controls, and websocket voice access are protected with role checks, rate limiting, and security logging.
- Future cloud secret delivery can be handled through direct environment injection or JSON secret bundles sourced from AWS Secrets Manager or Azure Key Vault.
