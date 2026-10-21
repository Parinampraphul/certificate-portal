# Certificate Portal

A lightweight web application for managing event participant lists, generating dynamic PDF certificates, and enabling self-service secure downloads via a time-limited public link.

---

## 🚀 Key Features

* **Admin Uploads:** Upload participant lists seamlessly to provision event credentials.
* **Secure Public Links:** Generate unique, event-specific claim links (`/claim/<event-slug>`) valid for 48 hours by default (fully customizable, with options to extend or disable anytime).
* **Self-Service Claim:** Participants enter their email, verify their name (with allowance for one correction), and instantly download their customized PDF certificate.
* **Automated Database Setup:** Integrated startup checks via `run.py` that automatically verify the SQL Server connection and create or update tables on launch.

---

## 🛠️ Tech Stack
* **Frontend & UI:** HTML5,CSS3,JavaScript
* **Backend:** Python
* **ORM/Database Driver:** SQLAlchemy/PyODBC/pymssql for communicating with MSSQL
* **Database:** MSSQL
* **PDF Generation:** Python PDF library (e.g., ReportLab / PyFPDF)

---

## 📋 Prerequisites

* Python 3.8 or higher installed on your machine.
* Microsoft SQL Server instance running and accessible.

---

## ⚙️ Setup & Installation

Follow these steps to run the project locally:

1. **Clone the repository and set up a virtual environment:**
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On macOS/Linux:
   source .venv/bin/activate

2.Install Dependencies:
 
 ```bash
  pip install -r requirements.txt
 ```

3.Configure environment variables:

  Copy the example environment file:

 ```bash
cp .env.example .env
 ```
  Open the newly created .env file and fill in your configuration details:

  DATABASE_URL (Your SQL Server connection string)

  ADMIN_PASSWORD (Secure password for admin panel access)

  SECRET_KEY (Secret key for session security)

  BASE_URL (Base URL for generated public links)

4.  Run the application:

 ```bash
python run.py
(This checks your SQL Server connection, automatically creates/updates tables, and starts the development server).
 ```
5. Access the portal:

Open your browser and navigate to: http://127.0.0.1:8000/admin

🔗 Public Claim Link
Format: BASE_URL/claim/<event-slug> (copy this directly from the admin event page).

Validity: Valid for 48 hours by default. Admins can extend or disable links at any time from the dashboard.

🎨 Certificate Customization
Background Design: The certificate background (including logos, signatories, and organizational branding) is located at:

app/static/assets/certificate_bg.png

Text Positioning & Layout: Text coordinates, font sizes, and bounding boxes can be adjusted at the top of:

app/certificate.py
