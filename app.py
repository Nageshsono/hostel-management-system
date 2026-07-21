from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,send_file
)
import io

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from database import get_db
from config import SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY
# =====================================
# LOGIN CHECK
# =====================================

def is_logged_in():
    return "user" in session
    # =====================================
# HOME
# =====================================

@app.route("/")
def home():

    if is_logged_in():
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))
    # =====================================
# REGISTER
# =====================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]
        confirm = request.form["confirm_password"]

        if password != confirm:
            flash("Passwords do not match")
            return redirect(url_for("register"))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM users WHERE username=%s",
            (username,)
        )

        user = cursor.fetchone()

        if user:
            flash("Username already exists")
            conn.close()
            return redirect(url_for("register"))

        hashed = generate_password_hash(password)

        cursor.execute(
            """
            INSERT INTO users(username,password,role)
            VALUES(%s,%s,%s)
            """,
            (username, hashed, "admin")
        )

        conn.commit()
        conn.close()

        flash("Registration Successful")

        return redirect(url_for("login"))

    return render_template("register.html")
    # =====================================
# LOGIN
# =====================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM users WHERE username=%s",
            (username,)
        )

        user = cursor.fetchone()

        conn.close()

        if user and check_password_hash(user["password"], password):

            session["user"] = user["username"]
            session["role"] = user["role"]

            flash("Login Successful")

            return redirect(url_for("dashboard"))

        flash("Invalid Username or Password")

    return render_template("login.html")
    # =====================================
# LOGOUT
# =====================================

@app.route("/logout")
def logout():

    session.clear()

    flash("Logged Out Successfully")

    return redirect(url_for("login"))
    # =====================================
# DASHBOARD
# =====================================
@app.route("/dashboard")
def dashboard():

    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Total Students
    cursor.execute("SELECT COUNT(*) AS total FROM students")
    total_students = cursor.fetchone()["total"]

    # Total Rooms
    total_rooms = 6

    # Present Today
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM attendance
        WHERE attendance_date = CURDATE()
        AND status='Present'
    """)
    present_today = cursor.fetchone()["total"]

    # Absent Today
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM attendance
        WHERE attendance_date = CURDATE()
        AND status='Absent'
    """)
    absent_today = cursor.fetchone()["total"]

    # Room Occupancy
    room_data = []

    for room in range(1, 7):
        cursor.execute(
            "SELECT COUNT(*) AS total FROM students WHERE room=%s",
            (room,)
        )

        room_data.append(cursor.fetchone()["total"])

    conn.close()

    return render_template(
        "dashboard.html",
        total_students=total_students,
        total_rooms=total_rooms,
        present_today=present_today,
        absent_today=absent_today,
        room_data=room_data
    )

# ADD STUDENT
# =====================================

@app.route("/add_student", methods=["GET", "POST"])
def add_student():

    if not is_logged_in():
        return redirect(url_for("login"))

    if request.method == "POST":

        name = request.form["name"]
        gender = request.form["gender"]
        mobile = request.form["mobile"]
        address = request.form["address"]
        room = request.form["room"]
        year = request.form["year"]
        department = request.form["department"]

        conn = get_db()
        cursor = conn.cursor()

        # Maximum 4 students per room
        cursor.execute(
            "SELECT COUNT(*) FROM students WHERE room=%s",
            (room,)
        )

        room_count = cursor.fetchone()[0]

        if room_count >= 4:
            flash(f"Room {room} is already full.")
            conn.close()
            return redirect(url_for("add_student"))

        cursor.execute("""
            INSERT INTO students
            (name, gender, mobile, address, room, year, department)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            name,
            gender,
            mobile,
            address,
            room,
            year,
            department
        ))

        conn.commit()
        conn.close()

        flash("Student Added Successfully")

        return redirect(url_for("students"))

    return render_template("add_student.html")
    # =====================================
# VIEW STUDENTS
# =====================================

@app.route("/students")
def students():

    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM students
        ORDER BY room, name
    """)

    students = cursor.fetchall()

    conn.close()

    return render_template(
        "students.html",
        students=students
    )
    # =====================================
# ROOMS
# =====================================

@app.route("/rooms")
def rooms():

    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    room_list = []

    for room in range(1, 7):

        cursor.execute(
            "SELECT * FROM students WHERE room=%s ORDER BY name",
            (room,)
        )

        students = cursor.fetchall()

        room_list.append({
            "room": room,
            "students": students,
            "count": len(students)
        })

    conn.close()

    return render_template(
        "rooms.html",
        room_list=room_list
    )
    # =====================================
# ATTENDANCE
# =====================================

# =====================================
# ATTENDANCE
# =====================================

from datetime import date

@app.route("/attendance", methods=["GET", "POST"])
def attendance():

    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    today = date.today()

    if request.method == "POST":

        cursor.execute("SELECT id FROM students")
        students = cursor.fetchall()

        for student in students:

            student_id = student["id"]

            status = request.form.get(f"status_{student_id}", "Absent")

            # Check if attendance already exists
            cursor.execute("""
                SELECT id
                FROM attendance
                WHERE student_id=%s
                AND attendance_date=%s
            """, (student_id, today))

            record = cursor.fetchone()

            if record:

                cursor.execute("""
                    UPDATE attendance
                    SET status=%s
                    WHERE id=%s
                """, (status, record["id"]))

            else:

                cursor.execute("""
                    INSERT INTO attendance
                    (student_id, attendance_date, status)
                    VALUES (%s,%s,%s)
                """, (
                    student_id,
                    today,
                    status
                ))

        conn.commit()
        conn.close()

        flash("Attendance Saved Successfully")

        return redirect(url_for("attendance"))

    cursor.execute("""
        SELECT *
        FROM students
        ORDER BY room,name
    """)

    students = cursor.fetchall()

    conn.close()

    return render_template(
        "attendance.html",
        students=students,
        today=today
    )
    # =====================================
# TODAY ATTENDANCE
# =====================================
@app.route("/today_attendance")
def today_attendance():

    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    today = date.today()

    cursor.execute("""
        SELECT
            students.name,
            students.room,
            attendance.status
        FROM attendance
        INNER JOIN students
            ON students.id = attendance.student_id
        WHERE attendance.attendance_date=%s
        ORDER BY students.room, students.name
    """, (today,))

    records = cursor.fetchall()

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM attendance
        WHERE attendance_date=%s
        AND status='Present'
    """, (today,))
    present_count = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM attendance
        WHERE attendance_date=%s
        AND status='Absent'
    """, (today,))
    absent_count = cursor.fetchone()["total"]

    conn.close()

    return render_template(
        "today_attendance.html",
        records=records,
        today=today,
        present_count=present_count,
        absent_count=absent_count
    )

    # =====================================
# ATTENDANCE REPORT
# =====================================

@app.route("/report")
def report():

    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    search = request.args.get("search", "")

    cursor.execute("""
        SELECT *
        FROM students
        WHERE name LIKE %s
        ORDER BY name
    """, ("%" + search + "%",))

    students = cursor.fetchall()

    reports = []

    for student in students:

        cursor.execute("""
            SELECT COUNT(*) AS present
            FROM attendance
            WHERE student_id=%s
            AND status='Present'
        """, (student["id"],))

        present = cursor.fetchone()["present"]

        cursor.execute("""
            SELECT COUNT(*) AS absent
            FROM attendance
            WHERE student_id=%s
            AND status='Absent'
        """, (student["id"],))

        absent = cursor.fetchone()["absent"]

        total = present + absent

        percentage = 0

        if total > 0:
            percentage = round((present / total) * 100, 2)

        reports.append({
            "name": student["name"],
            "room": student["room"],
            "department": student["department"],
            "year": student["year"],
            "present": present,
            "absent": absent,
            "percentage": percentage
        })

    conn.close()

    return render_template(
        "report.html",
        reports=reports,
        search=search
    )
    @app.route("/dashboard")
    def dashboard():

       if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Total students
    cursor.execute("SELECT COUNT(*) AS total FROM students")
    total_students = cursor.fetchone()["total"]

    # Present today
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM attendance
        WHERE attendance_date = CURDATE()
        AND status='Present'
    """)
    present_today = cursor.fetchone()["total"]

    # Absent today
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM attendance
        WHERE attendance_date = CURDATE()
        AND status='Absent'
    """)
    absent_today = cursor.fetchone()["total"]

    # Room Occupancy
    room_data = []

    for room in range(1, 7):

        cursor.execute(
            "SELECT COUNT(*) AS total FROM students WHERE room=%s",
            (room,)
        )

        count = cursor.fetchone()["total"]

        room_data.append(count)

    conn.close()

    return render_template(
        "dashboard.html",
        total_students=total_students,
        present_today=present_today,
        absent_today=absent_today,
        room_data=room_data
    )
    # =====================================
# STUDENT PROFILE
# =====================================

@app.route("/student/<int:id>")
def student_profile(id):

    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM students WHERE id=%s",
        (id,)
    )

    student = cursor.fetchone()

    conn.close()

    return render_template(
        "student_profile.html",
        student=student
    )
    # =====================================
# EXPORT ATTENDANCE REPORT TO PDF
# =====================================

@app.route("/export_pdf")
def export_pdf():

    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            students.name,
            students.room,
            students.department,
            students.year,
            attendance.attendance_date,
            attendance.status
        FROM attendance
        INNER JOIN students
        ON students.id = attendance.student_id
        ORDER BY attendance.attendance_date DESC
    """)

    records = cursor.fetchall()

    conn.close()

    buffer = io.BytesIO()

    pdf = SimpleDocTemplate(buffer)

    data = [[
        "Name",
        "Room",
        "Department",
        "Year",
        "Date",
        "Status"
    ]]

    for row in records:
        data.append([
            row["name"],
            row["room"],
            row["department"],
            row["year"],
            str(row["attendance_date"]),
            row["status"]
        ])

    table = Table(data)

    table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.grey),
        ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),

        ('GRID',(0,0),(-1,-1),1,colors.black),

        ('BACKGROUND',(0,1),(-1,-1),colors.beige),

        ('ALIGN',(0,0),(-1,-1),'CENTER'),

        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),

        ('BOTTOMPADDING',(0,0),(-1,0),12),
    ]))

    pdf.build([table])

    buffer.seek(0)

    return send_file(
        buffer,
        download_name="Attendance_Report.pdf",
        as_attachment=True,
        mimetype="application/pdf"
    )
    @app.route("/add_student", methods=["GET", "POST"])
    def add_student():

       if not is_logged_in():
        return redirect(url_for("login"))

    if request.method == "POST":

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO students
            (name, gender, mobile, address, room, year, department)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            request.form["name"],
            request.form["gender"],
            request.form["mobile"],
            request.form["address"],
            request.form["room"],
            request.form["year"],
            request.form["department"]
        ))

        conn.commit()
        conn.close()

        flash("Student Added Successfully")
        return redirect(url_for("students"))

    return render_template("add_student.html")
    from flask import request, render_template, redirect, url_for, flash

@app.route("/fees", methods=["GET", "POST"])
def fees():

    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Save Fee
    if request.method == "POST":

        student_id = request.form["student_id"]
        total_fee = float(request.form["total_fee"])
        paid_fee = float(request.form["paid_fee"])
        payment_date = request.form["payment_date"]
        payment_method = request.form["payment_method"]
        remarks = request.form["remarks"]

        due_fee = total_fee - paid_fee

        if due_fee <= 0:
            due_fee = 0
            status = "Paid"
        elif paid_fee == 0:
            status = "Pending"
        else:
            status = "Partial"

        cursor.execute("""
            INSERT INTO fees
            (student_id,total_fee,paid_fee,due_fee,payment_date,
             payment_method,payment_status,remarks)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            student_id,
            total_fee,
            paid_fee,
            due_fee,
            payment_date,
            payment_method,
            status,
            remarks
        ))

        conn.commit()
        flash("Fee added successfully!")

        return redirect(url_for("fees"))

    # Student dropdown
    cursor.execute("""
        SELECT id,name,room
        FROM students
        ORDER BY name
    """)
    students = cursor.fetchall()

    # Fee list
    cursor.execute("""
        SELECT
            fees.*,
            students.name,
            students.room
        FROM fees
        JOIN students
        ON fees.student_id = students.id
        ORDER BY fees.id DESC
    """)

    fees_data = cursor.fetchall()

    conn.close()

    return render_template(
        "fees.html",
        students=students,
        fees=fees_data
    )


    # =====================================
# MAIN
# =====================================

if __name__ == "__main__":
   app.run(host="0.0.0.0", port=5000, debug=True)