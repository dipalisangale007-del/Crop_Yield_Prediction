import requests
from flask import Flask, render_template, request, redirect, session, make_response, url_for
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Initialize the database
def init_db():
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()

    cur.execute(''' 
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            input TEXT,
            prediction TEXT,
            land_area REAL DEFAULT 0,
            current_crop TEXT DEFAULT ''
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS schemes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()

init_db()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']
        hashed_pwd = generate_password_hash(pwd)

        conn = sqlite3.connect('users.db')
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (uname, hashed_pwd))
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('register.html', error="Username already exists")
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']

        conn = sqlite3.connect('users.db')
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=?", (uname,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user[2], pwd):
            session['username'] = uname
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid Credentials")

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        return render_template('dashboard.html', user=session['username'])
    return redirect(url_for('login'))

@app.route('/predict', methods=['GET', 'POST'])
def predict():
    if 'username' not in session:
        return redirect(url_for('login'))

    error = None
    custom_message = None
    suggested_crop = None

    if request.method == 'POST':
        try:
            rainfall = float(request.form.get('rainfall', 0))
            temperature = float(request.form.get('temperature', 0))
            humidity = float(request.form.get('humidity', 0))
            soil_ph = float(request.form.get('soil_ph', 0))
            soil_moisture = float(request.form.get('soil_moisture', 0))
            fertilizer_usage = float(request.form.get('fertilizer_usage', 0))
            current_crop = request.form.get('current_crop', '').strip()
            land_area = float(request.form.get('land_area', 0))

            if not current_crop:
                error = "Please enter your currently planted crop."
                return render_template('predict.html', error=error)

            # Simple prediction logic
            if 25 <= temperature <= 35 and rainfall >= 300 and soil_ph >= 6.0:
                result = "High Yield Expected"
                suggested_crop = "Rice"
            elif 20 <= temperature <= 30 and rainfall >= 200 and 5.5 <= soil_ph < 6.5:
                result = "Moderate Yield Expected"
                suggested_crop = "Wheat"
            else:
                result = "Low Yield Expected"
                suggested_crop = "Millet"

            custom_message = f"You have planted {current_crop} over {land_area} acres. {result}."

            # Save prediction history
            conn = sqlite3.connect('users.db')
            cur = conn.cursor()

            input_summary = (f"Rainfall: {rainfall} mm, Temperature: {temperature}°C, "
                             f"Humidity: {humidity}%, Soil pH: {soil_ph}, Soil Moisture: {soil_moisture}%, "
                             f"Fertilizer Usage: {fertilizer_usage} kg, Current Crop: {current_crop}")

            prediction_summary = f"{custom_message} Suggested Crop: {suggested_crop}."

            cur.execute(
                "INSERT INTO history (user, input, prediction, land_area, current_crop) VALUES (?, ?, ?, ?, ?)",
                (session['username'], input_summary, prediction_summary, land_area, current_crop)
            )
            conn.commit()
            conn.close()

            return render_template('predict.html', custom_message=custom_message, suggested_crop=suggested_crop)

        except ValueError:
            error = "Please enter valid numerical values for all fields."
        except Exception as e:
            error = f"Something went wrong: {str(e)}"

    return render_template('predict.html', error=error)

@app.route('/history')
def history():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("SELECT input, prediction FROM history WHERE user=?", (session['username'],))
    rows = cur.fetchall()
    conn.close()

    parsed_data = []

    for input_str, prediction_str in rows:
        try:
            parts = dict(item.strip().split(": ", 1) for item in input_str.split(", "))
            rainfall = parts.get('Rainfall', 'N/A').replace(' mm', '')
            temperature = parts.get('Temperature', 'N/A').replace('°C', '')
            humidity = parts.get('Humidity', 'N/A').replace('%', '')
            soil_ph = parts.get('Soil pH', 'N/A')
            soil_moisture = parts.get('Soil Moisture', 'N/A').replace('%', '')
            fertilizer_usage = parts.get('Fertilizer Usage', 'N/A').replace(' kg', '')
            current_crop = parts.get('Current Crop', 'N/A')
            land_area = parts.get('Land Area', 'N/A')

            # Fake predicted yield and suggested crop extraction from prediction
            predicted_yield = "N/A"
            suggested_crop = "N/A"

            if "Suggested Crop:" in prediction_str:
                suggested_crop = prediction_str.split("Suggested Crop:")[-1].strip(" .")

            parsed_data.append((
                '', rainfall, temperature, humidity, soil_ph,
                soil_moisture, fertilizer_usage, current_crop,
                land_area, predicted_yield, suggested_crop, ''
            ))
        except Exception as e:
            print(f"Error parsing history record: {e}")

    return render_template('history.html', data=parsed_data)

@app.route('/download', methods=['POST'])
def download():
    prediction_text = request.form.get('prediction', 'No prediction available.')
    content = f"Crop Yield Report:\n{prediction_text}"

    response = make_response(content)
    response.headers["Content-Disposition"] = "attachment; filename=yield_report.txt"
    response.mimetype = 'text/plain'
    return response

@app.route('/chatbot', methods=['GET', 'POST'])
def chatbot():
    if 'username' not in session:
        return redirect(url_for('login'))

    answer = ""
    if request.method == 'POST':
        q = request.form['question'].lower()

        if "best crop" in q:
            answer = "Try rice, wheat, or soybean depending on your soil and weather."
        elif "disease" in q:
            answer = "Upload a leaf image to our crop scanner to detect diseases."
        elif "fertilizer" in q:
            answer = "NPK fertilizers are widely recommended, but it depends on your crop type."
        elif "pests" in q or "pest" in q:
            answer = "Use natural predators or appropriate pesticides to control pests."
        elif "rainfall" in q or "weather" in q:
            answer = "Check weather forecast websites for the latest updates."
        elif "soil" in q:
            answer = "Regular soil testing ensures good yield. Aim for a pH between 6-7 for most crops."
        elif "crop yield" in q:
            answer = "Crop yield depends on soil, weather, and farming practices. Predict it using our tool!"
        elif "current crop" in q:
            answer = "Tell me your current crop and I can assist you better."
        else:
            answer = "Sorry, I am still learning. Please ask about crops, pests, weather, or fertilizers."

    return render_template('chatbot.html', answer=answer)

@app.route('/schemes')
def schemes():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("SELECT title, description FROM schemes")
    schemes = cur.fetchall()
    conn.close()

    return render_template('schemes.html', schemes=schemes)

@app.route('/add_scheme', methods=['GET', 'POST'])
def add_scheme():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']

        conn = sqlite3.connect('users.db')
        cur = conn.cursor()
        cur.execute("INSERT INTO schemes (title, description) VALUES (?, ?)", (title, description))
        conn.commit()
        conn.close()

        return redirect(url_for('schemes'))

    return render_template('add_scheme.html')

@app.route('/weather', methods=['GET', 'POST'])
def weather():
    if 'username' not in session:
        return redirect(url_for('login'))

    weather = None

    if request.method == 'POST':
        city = request.form['city']
        api_key = '8450803a46da841233643f00c3766738'  # Replace this with your API Key
        weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"

        try:
            response = requests.get(weather_url)
            if response.status_code == 200:
                data = response.json()
                weather = {
                    'city': data['name'],
                    'temperature': data['main']['temp'],
                    'humidity': data['main']['humidity'],
                    'description': data['weather'][0]['description']
                }
            else:
                weather = {'city': city, 'temperature': '-', 'humidity': '-', 'description': 'City not found'}
        except requests.exceptions.RequestException as e:
            weather = {'city': city, 'temperature': '-', 'humidity': '-', 'description': f'Error: {str(e)}'}

    return render_template('weather.html', weather=weather)

@app.route('/encyclopedia')
def encyclopedia():
    if 'username' not in session:
        return redirect(url_for('login'))

    crops = {
        "Rice": "Staple food crop requiring lots of water and warm temperatures.",
        "Wheat": "Cereal grain grown in temperate climates, important for food security.",
        "Soybean": "Protein-rich legume used for oil and feed.",
        "Maize": "Also known as corn, used for food, feed, and industrial products.",
        "Cotton": "Fiber crop used in textile production."
    }

    return render_template('encyclopedia.html', crops=crops)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
