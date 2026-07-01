TakeCarHome — Local development README

Overview

TakeCarHome/CityPowerVehicle a local development setup to run the site on your machine.

Quick start

1. Open a PowerShell terminal in the repository root (where `manage.py` lives).

2. Create a virtual environment :

```powershell
python -m venv env
```

3. Activate the virtual environment:

```powershell
# PowerShell
env\Scripts\Activate.ps1
# or Command Prompt
# env\Scripts\activate.bat
```

4. Install dependencies:

```powershell
pip install -r requirements.txt
```

5. Apply database migrations:

```powershell
python manage.py migrate
```

6. Create a superuser (admin account) so you can log in to the admin and assign groups/users:

```powershell
python manage.py createsuperuser
```


7. Run the development server:

```powershell
python manage.py runserver
```

8. Open the site in your browser:

- Main site: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8000/admin/

