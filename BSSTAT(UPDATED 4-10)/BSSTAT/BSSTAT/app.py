import sys
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, g
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask import request
import arrow
from datetime import datetime, timedelta, timezone
app = Flask(__name__)
app.config['SECRET_KEY'] = 'tabakol'

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('CheckMate.db')
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    if 'db' in g:
        g.db.close()

# Create a table for user accounts 
with app.app_context():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            userid TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()

# Create a table for courses
with app.app_context():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS courses (
            course_id TEXT UNIQUE,
            course_name TEXT
        )
    ''')
    conn.commit()
    
# Create the 'events' table
with app.app_context():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT UNIQUE NOT NULL,
            event_name TEXT NOT NULL,
            event_date TEXT,
            event_location TEXT NOT NULL,
            present_sign_in_start TEXT,
            present_sign_in_end TEXT,
            late_sign_in_start TEXT,
            late_sign_in_end TEXT,
            present_sign_out_start TEXT,
            present_sign_out_end TEXT,
            late_sign_out_start TEXT,
            late_sign_out_end TEXT
        )
    ''')
    conn.commit()
    
# Create a table for students
with app.app_context():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT UNIQUE,
            student_name TEXT,
            student_mid TEXT,
            student_last TEXT,
            course_id TEXT REFERENCES courses(course_id) on DELETE CASCADE,
            year_level TEXT
        )
    ''')
    conn.commit()
    
# Create a table for attendance
with app.app_context():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            student_id TEXT REFERENCES students(student_id) ON DELETE CASCADE,
            student_name TEXT REFERENCES students(student_name),
            student_mid TEXT REFERENCES students(student_mid),
            student_last TEXT REFERENCES students(student_last),
            course_id TEXT REFERENCES students(course_id),
            year_level TEXT REFERENCES students(year_level),
            event_id TEXT REFERENCES events(event_id) ON DELETE CASCADE,
            event_date TEXT REFERENCES events(event_date),
            signin_time TEXT,
            signin_status TEXT,
            signout_time TEXT,
            signout_status TEXT,
            PRIMARY KEY (student_id, event_id)
        )
    ''')
    conn.commit()
    
# Create a trigger for cascading deletes on the attendance table
with app.app_context():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS delete_attendance
        AFTER DELETE ON students
        FOR EACH ROW
        BEGIN
            DELETE FROM attendance WHERE student_id = OLD.student_id;
        END;
    ''')
    conn.commit()

    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS delete_attendance_event
        AFTER DELETE ON events
        FOR EACH ROW
        BEGIN
            DELETE FROM attendance WHERE event_id = OLD.event_id;
        END;
    ''')
    conn.commit()
    
# Create a table for membership
with app.app_context():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS membership (
            membership_id INTEGER PRIMARY KEY,
            or_number TEXT,
            student_id TEXT,
            date_of_payment TEXT,
            semester TEXT,
            amount TEXT,
            mode_of_payment TEXT,
            receiver TEXT,
            CONSTRAINT unique_student_semester UNIQUE (student_id, semester)
        )
    ''')
    conn.commit()


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if 'userId' not in request.form or 'password' not in request.form:
            flash('Invalid request. Please provide both User ID and password.', 'error')
            return redirect(url_for('login'))

        user_id = request.form['userId']
        password = request.form['password']

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM users WHERE userid = ?', (user_id,))
        user = cursor.fetchone()

        if user is None:
            flash('Invalid credentials. Please check your User ID and password.', 'error')
            conn.close()
            return redirect(url_for('login'))

        stored_password = user[2]
        if not check_password_hash(stored_password, password):
            flash('Invalid credentials. Please check your User ID and password.', 'error')
            conn.close()
            return redirect(url_for('login'))

        session['user_id'] = user_id
        conn.close()

        flash('Login successful!', 'success')

        # Debug prints
        print(f"Redirecting to dashboard for user: {user_id}")
        print(f"Current app context: {current_app.name}")

        return redirect(url_for('dashboard'))  # Redirect to dashboard after login

    return render_template('login.html')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/team')
def team():
    return render_template('team.html')


@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(course_id) FROM courses")
    total_courses = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(student_id) FROM students")
    total_students = cursor.fetchone()[0]

    conn.close()

    return render_template("dashboard.html", total_courses=total_courses, total_students=total_students)

@app.route("/total_courses", methods=["GET"])
def get_course_count():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(course_id) FROM courses")
    total_courses = cursor.fetchone()[0]
    conn.close()
    return jsonify({"total_courses": total_courses})

@app.route("/total_students", methods=["GET"])
def get_student_count():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(student_id) FROM students")
    total_students = cursor.fetchone()[0]
    conn.close()
    return jsonify({"total_students": total_students})


@app.route('/check_user_id')
def check_user_id():
    user_id = request.args.get('userId')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT userid FROM users WHERE userid = ?', (user_id,))
    result = cursor.fetchone()

    conn.close()

    if result:
        return 'exists'  # User ID exists in the database
    else:
        return 'unique'  # User ID doesn't exist in the database

# Function to handle account creation
@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
    if request.method == 'POST':
        userid = request.form['userId']
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirmPassword']

        # Validate form data
        if not all([userid, username, password, confirm_password]):
            flash('Please fill in all fields.', 'error')
            return redirect(url_for('index'))

        if len(password) < 8:
            flash('Password should have at least 8 characters.', 'error')
            return redirect(url_for('index'))

        if password != confirm_password:
            flash('Password mismatch. Please confirm your password correctly.', 'error')
            return redirect(url_for('index'))

        # Check if the user already exists
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE userid = ?', (userid,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash('User ID already exists. Please choose a different one.', 'error')
            conn.close()
            return redirect(url_for('index'))

        # Insert the new user into the database
        try:
            cursor.execute('INSERT INTO users (userid, username, password) VALUES (?, ?, ?)', (userid, username, password))
            conn.commit()
            conn.close()
            flash('Account created successfully!', 'success')
            return redirect(url_for('login'))
        except sqlite3.Error as e:
            conn.rollback()
            conn.close()
            flash(f'Error creating account: {str(e)}', 'error')
            return redirect(url_for('index'))

    return render_template('create_account.html')

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    print("Change password route accessed")  # Add this line for debugging

    if request.method == 'POST':
        user_id = request.form['userid']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        print(f"Received form data - User ID: {user_id}, Password: {password}, Confirm Password: {confirm_password}")

        conn = sqlite3.connect('CheckMate.db')
        cursor = conn.cursor()

        if not user_id or not password or not confirm_password:
            flash('Please fill in all fields.', 'error')
            print("Form data incomplete.")
            conn.close()
            return render_template('change_password.html')  # Return to the same page with the error message
        elif len(password) < 8:
            flash('Password should have at least 8 characters.', 'error')
            print("Password length less than 8 characters.")
            conn.close()
            return render_template('change_password.html')  # Return to the same page with the error message
        elif password != confirm_password:
            flash('Password mismatch. Please confirm your password correctly.', 'error')
            print("Password mismatch.")
            conn.close()
            return render_template('change_password.html')  # Return to the same page with the error message
        else:
            cursor.execute('SELECT userid FROM users WHERE userid = ?', (user_id,))
            result = cursor.fetchone()
            if result is None:
                flash('User ID does not exist. Please enter a valid User ID.', 'error')
                print("User ID not found.")
                conn.close()
                return render_template('change_password.html')  # Return to the same page with the error message

            try:
                cursor.execute('UPDATE users SET password = ? WHERE userid = ?', (password, user_id))
                conn.commit()
                print("Password updated successfully!")
                flash('Password changed successfully!', 'success')
            except sqlite3.Error as e:
                conn.rollback()
                print(f'Error updating password: {str(e)}')
                flash('Error updating password. Please try again.', 'error')

        conn.close()

    return render_template('change_password.html')

@app.route('/validate_login', methods=['POST'])
def validate_login():
    data = request.get_json()
    user_id = data.get('userId')
    password = data.get('password')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM users WHERE userid = ?', (user_id,))
    user = cursor.fetchone()

    conn.close()

    if user is None:
        # User ID not found in the database
        return jsonify({'message': 'not_exist'})

    stored_password = user[2]  # Assuming password is stored in the third column

    if password != stored_password:
        # Incorrect password
        return jsonify({'message': 'incorrect_password'})

    # Valid credentials
    session['user_id'] = user_id  # Set user session to indicate the user is logged in
    return jsonify({'message': 'success', 'redirect_url': url_for('dashboard')})

@app.route('/create_course', methods=['POST'])
def create_course():
    try:
        course_name = request.form.get('courseName')
        course_id = request.form.get('courseId')

        # Validate input data if needed

        # Check if the course already exists
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM courses WHERE course_id = ?', (course_id,))
        existing_course = cursor.fetchone()

        if existing_course:
            conn.close()
            return jsonify({'error': 'Course ID already exists'}), 400

        # Insert the new course into the database
        cursor.execute('INSERT INTO courses (course_id, course_name) VALUES (?, ?)', (course_id, course_name))
        conn.commit()
        conn.close()

        return jsonify({'message': 'Course created successfully'})
    except sqlite3.Error as e:
        app.logger.error(f"SQLite error: {str(e)}")
        app.logger.exception(e)  # Log the complete stack trace
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        app.logger.error(f"Unexpected error: {str(e)}")
        app.logger.exception(e)  # Log the complete stack trace
        return jsonify({'error': 'An unexpected error occurred'}), 500

@app.route('/update_course/<course_id>', methods=['POST'])
def update_course(course_id):
    try:
        updated_course_name = request.form.get('updatedCourseName')

        # Validate input data if needed

        # Update the course in the database
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE courses SET course_name = ? WHERE course_id = ?', (updated_course_name, course_id))
        conn.commit()
        conn.close()

        return jsonify({'message': 'Course updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete_course/<course_id>', methods=['POST'])
def delete_course(course_id):
    try:
        # Delete the course from the database
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM courses WHERE course_id = ?', (course_id,))
        conn.commit()
        conn.close()

        return jsonify({'message': 'Course deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/clear_course/<course_id>', methods=['POST'])
def clear_course(course_id):
    try:
        # Implement the logic to clear a course based on your requirements
        # This might involve resetting some values or removing associated data

        # You can use the following JavaScript to clear the input fields on the client side
        clear_script = """
        <script>
            document.getElementById("courseName").value = "";
            document.getElementById("courseId").value = "";
            // Add more lines for other input fields as needed
        </script>
        """
        
        # Return the response with the JavaScript code
        return render_template_string(clear_script, message='Course cleared successfully')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/student')
@login_required
def student():
    return render_template('student.html')

@app.route('/create_student', methods=['POST'])
def create_student():
    try:
        student_id = request.form.get('studentId')
        student_name = request.form.get('studentname')
        student_mid = request.form.get('studentmid')
        student_last = request.form.get('studentlast')
        course_id = request.form.get('courseid')
        year_level = request.form.get('yearlevel')

        # Validate input data if needed

        # Check if the student already exists
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
        existing_student = cursor.fetchone()

        if existing_student:
            conn.close()
            return jsonify({'error': 'Student ID already exists'}), 400

        # Check if the course_id exists in the courses table
        cursor.execute('SELECT * FROM courses WHERE course_id = ?', (course_id,))
        existing_course = cursor.fetchone()

        if not existing_course:
            conn.close()
            return jsonify({'error': 'Course ID does not exist'}), 400

        # Insert the new student into the database
        cursor.execute('''
            INSERT INTO students (
                student_id, student_name, student_mid, student_last, course_id, year_level
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            student_id, student_name, student_mid, student_last, course_id, year_level
        ))
        conn.commit()
        conn.close()

        return jsonify({'message': 'Student created successfully'})
    except sqlite3.Error as e:
        app.logger.error(f"SQLite error: {str(e)}")
        app.logger.exception(e)  # Log the complete stack trace
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        app.logger.error(f"Unexpected error: {str(e)}")
        app.logger.exception(e)  # Log the complete stack trace
        return jsonify({'error': 'An unexpected error occurred'}), 500

@app.route('/update_student/<student_id>', methods=['POST'])
def update_student(student_id):
    try:
        # Get the updated data from the request
        updated_student_name = request.form.get('updatedStudentName')
        updated_student_mid = request.form.get('updatedStudentMid')
        updated_student_last = request.form.get('updatedStudentLast')
        updated_course_id = request.form.get('updatedCourseId')
        updated_year_level = request.form.get('updatedYearLevel')

        # Validate input data if needed

        # Check if the updated_course_id exists in the courses table
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM courses WHERE course_id = ?', (updated_course_id,))
        existing_course = cursor.fetchone()

        if not existing_course:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Course code does not exist. Please enter a valid course code.'}), 400

        # Update the student in the database
        cursor.execute('''
            UPDATE students SET
                student_name = ?,
                student_mid = ?,
                student_last = ?,
                course_id = ?,
                year_level = ?
            WHERE student_id = ?
        ''', (
            updated_student_name,
            updated_student_mid,
            updated_student_last,
            updated_course_id,
            updated_year_level,
            student_id
        ))
        conn.commit()

        # Close the cursor and connection after use
        cursor.close()
        conn.close()

        return jsonify({'message': 'Student updated successfully'})
    except Exception as e:
        print('Error:', str(e))  # Add this line for debugging
        return jsonify({'error': str(e)}), 500


    
@app.route('/delete_student/<student_id>', methods=['POST'])
def delete_student(student_id):
    try:
        # Connect to the database
        conn = get_db() 
        cursor = conn.cursor()

        # Check if the student exists
        cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
        existing_student = cursor.fetchone()

        if not existing_student:
            conn.close()
            return jsonify({'error': 'Student not found'}), 404

        # Delete the student from the database
        cursor.execute('DELETE FROM students WHERE student_id = ?', (student_id,))
        conn.commit()
        conn.close()

        return jsonify({'message': 'Student deleted successfully'})
    except Exception as e:
        print('Error:', str(e))  # Add this line for debugging
        return jsonify({'error': str(e)}), 500
    
@app.route('/get_students', methods=['GET'])
def get_students():
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM students')
        rows = cursor.fetchall()

        # Convert the result to a list of dictionaries for JSON response
        students = []
        for row in rows:
            student = {
                'student_id': row[0],
                'student_name': row[1],
                'student_mid': row[2],
                'student_last': row[3],
                'course_id': row[4],
                'year_level': row[5],
            }
            students.append(student)

        return jsonify(students=students)
    
@app.route('/search_students', methods=['GET'])
def search_students():
    try:
        search_query = request.args.get('search', '').lower()

        # Connect to the database
        conn = get_db()
        cursor = conn.cursor()

        # Perform the search query
        cursor.execute('''
            SELECT * FROM students
            WHERE LOWER(student_id) LIKE ? OR LOWER(student_name) LIKE ? OR LOWER(student_mid) LIKE ? OR LOWER(student_last) LIKE ? OR LOWER(course_id) LIKE ? OR LOWER(year_level) LIKE ?
        ''', ('%' + search_query + '%', '%' + search_query + '%', '%' + search_query + '%', '%' + search_query + '%', '%' + search_query + '%', '%' + search_query + '%'))
        rows = cursor.fetchall()

        # Convert the result to a list of dictionaries for JSON response
        students = []
        for row in rows:
            student = {
                'student_id': row[0],
                'student_name': row[1],
                'student_mid': row[2],
                'student_last': row[3],
                'course_id': row[4],
                'year_level': row[5],
            }
            students.append(student)

        # Close the cursor and connection after use
        cursor.close()
        conn.close()

        return jsonify(students=students)
    except Exception as e:
        print('Error:', str(e))  # For debugging
        return jsonify({'error': 'An unexpected error occurred'}), 500
    
@app.route('/courses')
@login_required
def courses():
    conn = get_db()
    cursor = conn.cursor()

    # Fetch all courses from the database
    cursor.execute('SELECT * FROM courses')
    courses = cursor.fetchall()

    conn.close()

    return render_template('courses.html', courses=courses)
@app.route('/get_courses')
def get_courses():
    conn = get_db()
    cursor = conn.cursor()

    # Fetch all courses from the database
    cursor.execute('SELECT * FROM courses')
    courses = cursor.fetchall()

    conn.close()

    # Convert the courses to a list of dictionaries
    courses_list = [{'course_id': course['course_id'], 'course_name': course['course_name']} for course in courses]

    return jsonify(courses_list)

@app.route('/events')
@login_required
def events():
    return render_template('events.html')

@app.route('/create_event', methods=['POST'])
def create_event():
    data = request.get_json()

    # Extract data from the JSON payload
    eventID = data.get("eventID")
    eventName = data.get("eventName")
    eventDate = data.get("eventDate")
    eventLocation = data.get("eventLocation")
    PStartTime = data.get("PStartTime")
    PEndTime = data.get("PEndTime")
    LStartTime = data.get("LStartTime")
    LEndTime = data.get("LEndTime")
    PSOStartTime = data.get("PSOStartTime")
    PSOEndTime = data.get("PSOEndTime")
    LSOStartTime = data.get("LSOStartTime")
    LSOEndTime = data.get("LSOEndTime")
    
    # Check if start time is before end time for all time ranges
    if not isValidTimeRange(PStartTime, PEndTime) or \
       not isValidTimeRange(LStartTime, LEndTime) or \
       not isValidTimeRange(PSOStartTime, PSOEndTime) or \
       not isValidTimeRange(LSOStartTime, LSOEndTime):
        return jsonify({'error': 'Invalid time ranges'})

    # Check if the event ID already exists
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM events WHERE event_id = ?', (eventID,))
        existing_event = cursor.fetchone()

        if existing_event:
            # Event ID already exists, return an error message
            return jsonify({"message": "Event ID already exists", "error": True}), 400

        # Insert data into the 'events' table
        cursor.execute('''
            INSERT INTO events (
                event_id, event_name, event_date, event_location,
                present_sign_in_start, present_sign_in_end,
                late_sign_in_start, late_sign_in_end,
                present_sign_out_start, present_sign_out_end,
                late_sign_out_start, late_sign_out_end
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            eventID, eventName, eventDate, eventLocation,
            PStartTime, PEndTime, LStartTime, LEndTime,
            PSOStartTime, PSOEndTime, LSOStartTime, LSOEndTime
        ))
        conn.commit()

    return jsonify({"message": "Event created successfully", "error": False})

@app.route('/update_event', methods=['POST'])
def update_event():
    data = request.get_json()

    # Extract data from the JSON payload
    eventID = data.get("eventID")
    eventName = data.get("eventName")
    eventDate = data.get("eventDate")
    eventLocation = data.get("eventLocation")
    PStartTime = data.get("PStartTime")
    PEndTime = data.get("PEndTime")
    LStartTime = data.get("LStartTime")
    LEndTime = data.get("LEndTime")
    PSOStartTime = data.get("PSOStartTime")
    PSOEndTime = data.get("PSOEndTime")
    LSOStartTime = data.get("LSOStartTime")
    LSOEndTime = data.get("LSOEndTime")

    # Check if start time is before end time for all time ranges
    if not isValidTimeRange(PStartTime, PEndTime) or \
    not isValidTimeRange(LStartTime, LEndTime) or \
    not isValidTimeRange(PSOStartTime, PSOEndTime) or \
    not isValidTimeRange(LSOStartTime, LSOEndTime):
        return jsonify({'error': 'Invalid time ranges'})


    # Check if the event ID exists
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM events WHERE event_id = ?', (eventID,))
        existing_event = cursor.fetchone()

        if not existing_event:
            # Event ID does not exist, return an error message
            return jsonify({"message": "Event ID does not exist", "error": True}), 404

        # Update data in the 'events' table
        cursor.execute('''
            UPDATE events
            SET
                event_name = ?,
                event_date = ?,
                event_location = ?,
                present_sign_in_start = ?,
                present_sign_in_end = ?,
                late_sign_in_start = ?,
                late_sign_in_end = ?,
                present_sign_out_start = ?,
                present_sign_out_end = ?,
                late_sign_out_start = ?,
                late_sign_out_end = ?
            WHERE event_id = ?
        ''', (
            eventName, eventDate, eventLocation,
            PStartTime, PEndTime, LStartTime, LEndTime,
            PSOStartTime, PSOEndTime, LSOStartTime, LSOEndTime,
            eventID
        ))
        conn.commit()

    return jsonify({"message": "Event updated successfully", "error": False})

# Function to check if start time is before end time
def isValidTimeRange(startTime, endTime):
    return compareTime(startTime, endTime) < 0

# Function to compare two time strings (HH:MM format)
def compareTime(time1, time2):
    t1 = convertToMinutes(time1)
    t2 = convertToMinutes(time2)
    return t1 - t2

# Function to convert time string to minutes
def convertToMinutes(time):
    parts = time.split(":")
    return int(parts[0]) * 60 + int(parts[1])

@app.route('/delete_event', methods=['POST'])
def delete_event():
    data = request.get_json()

    # Extract event ID from the JSON payload
    eventID = data.get("eventID")

    # Check if the event ID exists
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM events WHERE event_id = ?', (eventID,))
        existing_event = cursor.fetchone()

        if not existing_event:
            # Event ID does not exist, return an error message
            return jsonify({"message": "Event ID does not exist", "error": True}), 404

        # Delete the event from the 'events' table
        cursor.execute('DELETE FROM events WHERE event_id = ?', (eventID,))
        conn.commit()

    return jsonify({"message": "Event deleted successfully", "error": False})

@app.route('/get_events', methods=['GET'])
def get_events():
    with app.app_context():
        conn = get_db()  # Assuming you have a function like get_db to get the database connection
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM events')
        rows = cursor.fetchall()

        # Convert the result to a list of dictionaries for JSON response
        events = []
        for row in rows:
            event = {
                'eventID': row[0],
                'eventName': row[1],
                'eventDate': str(row[2]),
                'eventLocation': row[3],
                'PStartTime': str(row[4]),
                'PEndTime': str(row[5]),
                'LStartTime': str(row[6]),
                'LEndTime': str(row[7]),
                'PSOStartTime': str(row[8]),
                'PSOEndTime': str(row[9]),
                'LSOStartTime': str(row[10]),
                'LSOEndTime': str(row[11]),
            }
            events.append(event)

        return jsonify(events=events)
    
@app.route('/attendance')
def attendance():
    return render_template('attendance.html')

@app.route('/sign_in', methods=['POST'])
def sign_in():
    if request.method == 'POST':
        student_id = request.form.get('studentId')
        event_id = request.form.get('eventId')

        # Check if both student_id and event_id are provided
        if student_id and event_id:
            # Fetch student data from the students table
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
            student_data = cursor.fetchone()

            if student_data:
                # Fetch event data from the events table
                cursor.execute('SELECT * FROM events WHERE event_id = ?', (event_id,))
                event_data = cursor.fetchone()

                if event_data:
                    # Convert the local timestamp to a UTC timestamp with UTC+8
                    local_timestamp = datetime.now(timezone(timedelta(hours=8)))

                    # Check if the sign-in time is within the specified intervals
                    present_sign_in_start = event_data['present_sign_in_start']
                    present_sign_in_end = event_data['present_sign_in_end']
                    late_sign_in_start = event_data['late_sign_in_start']
                    late_sign_in_end = event_data['late_sign_in_end']

                    sign_in_time = local_timestamp.strftime('%H:%M:%S')

                    # Print statements for debugging
                    print(f"Student ID: {student_id}")
                    print(f"Event ID: {event_id}")
                    print(f"Local Timestamp: {local_timestamp}")
                    print(f"Sign-in Time: {sign_in_time}")
                    print(f"Present Sign-in Start: {present_sign_in_start}, Present Sign-in End: {present_sign_in_end}")
                    print(f"Late Sign-in Start: {late_sign_in_start}, Late Sign-in End: {late_sign_in_end}")

                    if present_sign_in_start <= sign_in_time <= present_sign_in_end:
                        signin_status = 'Present'
                    elif late_sign_in_start <= sign_in_time <= late_sign_in_end:
                        signin_status = 'Late'
                    else:
                        signin_status = 'Absent'

                    # Insert attendance record into the attendance table
                    try:
                        cursor.execute('''
                            INSERT INTO attendance (
                                student_id, student_name, student_mid, student_last, 
                                course_id, year_level, event_id, event_date, 
                                signin_time, signin_status, signout_time, signout_status
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                        ''', (
                            student_data['student_id'], student_data['student_name'],
                            student_data['student_mid'], student_data['student_last'],
                            student_data['course_id'], student_data['year_level'],
                            event_data['event_id'], event_data['event_date'],
                            local_timestamp.strftime('%Y-%m-%d %H:%M:%S'), signin_status
                        ))
                        conn.commit()

                        return f"Sign-in successful! Sign-in status: {signin_status}"

                    except Exception as e:
                        return f"Error! You can only sign-in into an event once."

                else:
                    return "Event not found."

            else:
                return "Student not found."

        else:
            return "Both student ID and event ID are required."
        
@app.route('/sign_out', methods=['POST'])
def sign_out():
    if request.method == 'POST':
        student_id = request.form.get('studentId')
        event_id = request.form.get('eventId')

        # Check if both student_id and event_id are provided
        if student_id and event_id:
            # Fetch event data from the events table
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM events WHERE event_id = ?', (event_id,))
            event_data = cursor.fetchone()

            # Fetch student data based on student_id
            cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
            student_data = cursor.fetchone()

            if event_data and student_data:
                # Convert the local timestamp to a UTC timestamp with UTC+8
                local_timestamp = datetime.now(timezone(timedelta(hours=8)))

                # Check if the sign-out time is within the specified intervals
                present_sign_out_start = event_data['present_sign_out_start']
                present_sign_out_end = event_data['present_sign_out_end']
                late_sign_out_start = event_data['late_sign_out_start']
                late_sign_out_end = event_data['late_sign_out_end']

                sign_out_time = local_timestamp.strftime('%H:%M:%S')

                # Fetch additional student information
                student_name = student_data['student_name']
                student_mid = student_data['student_mid']
                student_last = student_data['student_last']
                course_id = student_data['course_id']
                year_level = student_data['year_level']
                event_date = event_data['event_date']  # Assuming event_date is in the events table

                # Print statements for debugging
                print(f"Student ID: {student_id}")
                print(f"Event ID: {event_id}")
                print(f"Local Timestamp: {local_timestamp}")
                print(f"Sign-out Time: {sign_out_time}")
                print(f"Present Sign-out Start: {present_sign_out_start}, Present Sign-out End: {present_sign_out_end}")
                print(f"Late Sign-out Start: {late_sign_out_start}, Late Sign-out End: {late_sign_out_end}")

                if present_sign_out_start <= sign_out_time <= present_sign_out_end:
                    signout_status = 'Present'
                elif late_sign_out_start <= sign_out_time <= late_sign_out_end:
                    signout_status = 'Late'
                else:
                    signout_status = 'Absent'

                # Fetch additional student information
                student_name = student_data['student_name']
                student_mid = student_data['student_mid']
                student_last = student_data['student_last']
                course_id = student_data['course_id']
                year_level = student_data['year_level']
                event_date = event_data['event_date']  # Assuming event_date is in the events table

                # Check if there is an existing attendance record
                cursor.execute('SELECT * FROM attendance WHERE student_id = ? AND event_id = ?', (student_id, event_id))
                existing_record = cursor.fetchone()

                if existing_record:
                    # Update the existing attendance record
                    try:
                        cursor.execute('''
                            UPDATE attendance 
                            SET signout_time = ?, signout_status = ? 
                            WHERE student_id = ? AND event_id = ?
                        ''', (
                            local_timestamp.strftime('%Y-%m-%d %H:%M:%S'), signout_status,
                            student_id, event_id
                        ))
                        conn.commit()

                        return f"Sign-out successful! Sign-out status: {signout_status}"

                    except Exception as e:
                        print(f"Error updating the attendance table: {str(e)}")
                        return f"Error updating the attendance table: {str(e)}"
                else:
                    # Insert a new attendance record
                    try:
                        cursor.execute('''
                            INSERT INTO attendance (
                                student_id, student_name, student_mid, student_last, 
                                course_id, year_level, event_id, event_date, 
                                signin_time, signin_status, signout_time, signout_status
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
                        ''', (
                            student_id, student_name, student_mid, student_last,
                            course_id, year_level, event_id, event_date,
                            local_timestamp.strftime('%Y-%m-%d %H:%M:%S'), signout_status
                        ))
                        conn.commit()

                        return f"Sign-out successful! Sign-out status: {signout_status}"

                    except Exception as e:
                        print(f"Error inserting into the attendance table: {str(e)}")
                        return f"Error inserting into the attendance table: {str(e)}"

            else:
                return "Event not found or student not found."

        else:
            return "Both student ID and event ID are required."


@app.route('/get_attendance_data', methods=['GET'])
def get_attendance_data():
    try:
        # Connect to the database
        conn = get_db()
        cursor = conn.cursor()

        # Fetch data from the attendance table
        cursor.execute('SELECT * FROM attendance')
        rows = cursor.fetchall()

        # Convert the result to a list of dictionaries for JSON response
        attendance_data = []
        for row in rows:
            attendance_record = {
                'student_id': row[0],
                'student_name': row[1],
                'student_mid': row[2],
                'student_last': row[3],
                'course_id': row[4],
                'year_level': row[5],
                'event_id': row[6],
                'event_date': row[7],
                'signin_time': row[8],
                'signin_status': row[9],
                'signout_time': row[10],
                'signout_status': row[11],
            }
            attendance_data.append(attendance_record)

        # Close the database connection
        conn.close()

        # Return the attendance data as JSON
        return jsonify(attendance_data=attendance_data)

    except Exception as e:
        return str(e)


@app.route('/delete_attendance', methods=['POST'])
def delete_attendance():
    try:
        # Retrieve student_id and event_id from the request
        student_id = request.form.get('studentId')
        event_id = request.form.get('eventId')

        # Delete the attendance record from the database
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM attendance WHERE student_id = ? AND event_id = ?', (student_id, event_id))
        conn.commit()
        conn.close()

        return jsonify({'message': 'Attendance record deleted successfully'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


        
@app.route('/membership')
@login_required
def membership():
    return render_template('membership.html')

@app.route('/membership-data')
def get_membership_data():
    try:
        conn = sqlite3.connect('checkmate.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM membership')
        data = cursor.fetchall()
        conn.close()
        return jsonify({'data': data})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/register-membership', methods=['POST'])
def register_membership():
    try:
        # Retrieve registration data from the form
        or_number = request.form['ORNumber']
        student_id = request.form['StudentId']
        amount = request.form['Amount']
        mode = request.form['Mode']
        semester = request.form['Semester']
        receiver = request.form['Receiver']

        # Get current date and time
        current_date = datetime.now().strftime('%Y-%m-%d')

        # Check if the OR number already exists
        conn = sqlite3.connect('checkmate.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM membership WHERE or_number = ?', (or_number,))
        existing_or = cursor.fetchone()

        if existing_or:
            conn.close()
            return jsonify(message="OR Number already exists")

        # Check if the student ID is already registered for the current semester
        cursor.execute('SELECT * FROM membership WHERE student_id = ? AND semester = ?', (student_id, semester))
        existing_record = cursor.fetchone()

        if existing_record:
            conn.close()
            return jsonify(message="Student Already Paid")

        # Insert registration data into the database
        cursor.execute('''
            INSERT INTO membership (or_number, student_id, amount, mode_of_payment, semester, receiver, date_of_payment)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (or_number, student_id, amount, mode, semester, receiver, current_date))
        conn.commit()
        conn.close()

        return jsonify(message="Registration successful")
    except Exception as e:
        return jsonify(message=f"Failed to register membership. Error: {e}")

@app.route("/total_memberships", methods=["GET"])
def get_membership_count():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(membership_id) FROM membership")
    total_memberships = cursor.fetchone()[0]
    conn.close()
    return jsonify({"total_memberships": total_memberships})

@app.route('/delete-membership', methods=['POST'])
def delete_membership():
    try:
        # Retrieve the OR number of the membership record to be deleted from the request
        or_number = request.form['ORNumber']

        # Connect to the database
        conn = get_db()
        cursor = conn.cursor()

        # Check if the membership record exists
        cursor.execute('SELECT * FROM membership WHERE or_number = ?', (or_number,))
        existing_record = cursor.fetchone()

        if existing_record:
            # Delete the membership record
            cursor.execute('DELETE FROM membership WHERE or_number = ?', (or_number,))
            
            conn.commit()
            conn.close()
            return jsonify(message="Membership record deleted successfully")
        else:
            # If the record does not exist, return an error message
            conn.close()
            return jsonify(message="Membership record not found")
    except Exception as e:
        return jsonify(message=f"Failed to delete membership record. Error: {e}")

@app.route('/search-membership', methods=['POST'])
def search_membership():
    try:
        search_term = request.form['searchTerm']
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM membership WHERE or_number LIKE ? OR student_id LIKE ?", ('%' + search_term + '%', '%' + search_term + '%'))
        data = cursor.fetchall()
        conn.close()
        return jsonify({'data': [dict(row) for row in data]})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/exit')
def exit_app():
    sys.exit("Exiting the application")

if __name__ == '__main__':
    app.run(debug=True)
