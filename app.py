import os
from datetime import datetime, date, time
from zoneinfo import ZoneInfo
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "change-this-secret-before-deploying"
)

db_url = os.environ.get("DATABASE_URL", "sqlite:///basra_attendance.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

SCHOOL_NAME = "BASRA INTERNATIONAL ACADEMY"
SOMALIA_TZ = ZoneInfo("Africa/Mogadishu")


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="teacher")
    active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_code = db.Column(db.String(40), unique=True, nullable=False)
    full_name = db.Column(db.String(160), nullable=False)
    class_name = db.Column(db.String(80), nullable=False)
    active = db.Column(db.Boolean, default=True)


class Period(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    weekday = db.Column(db.Integer, nullable=False, default=0)  # 0 = every school day


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    period_id = db.Column(db.Integer, db.ForeignKey("period.id"), nullable=False)
    attendance_date = db.Column(db.Date, nullable=False, default=date.today)
    status = db.Column(db.String(20), nullable=False)
    marked_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    marked_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(SOMALIA_TZ).replace(tzinfo=None)
    )

    student = db.relationship("Student")
    period = db.relationship("Period")
    user = db.relationship("User")

    __table_args__ = (
        db.UniqueConstraint(
            "student_id", "period_id", "attendance_date",
            name="unique_student_period_date"
        ),
    )


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "admin":
            flash("Boggan waxaa geli kara Admin oo keliya.", "error")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)
    return wrapped


def current_period():
    now = datetime.now(SOMALIA_TZ).time().replace(tzinfo=None)
    today_weekday = datetime.now(SOMALIA_TZ).weekday() + 1
    periods = Period.query.order_by(Period.start_time).all()

    for period in periods:
        if (
            period.start_time <= now < period.end_time
            and period.weekday in (0, today_weekday)
        ):
            return period
    return None


@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username, active=True).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("dashboard"))

        flash("Username ama password waa khalad.", "error")

    return render_template("login.html", school_name=SCHOOL_NAME)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    today = datetime.now(SOMALIA_TZ).date()
    period = current_period()
    total_students = Student.query.filter_by(active=True).count()
    today_records = Attendance.query.filter_by(attendance_date=today).count()
    absent_today = Attendance.query.filter_by(
        attendance_date=today, status="Absent"
    ).count()
    recent = (
        Attendance.query.filter_by(attendance_date=today)
        .order_by(Attendance.marked_at.desc())
        .limit(12)
        .all()
    )

    return render_template(
        "dashboard.html",
        school_name=SCHOOL_NAME,
        period=period,
        total_students=total_students,
        today_records=today_records,
        absent_today=absent_today,
        recent=recent,
        today=today
    )


@app.route("/students", methods=["GET", "POST"])
@admin_required
def students():
    if request.method == "POST":
        code = request.form.get("student_code", "").strip()
        name = request.form.get("full_name", "").strip()
        class_name = request.form.get("class_name", "").strip()

        if not code or not name or not class_name:
            flash("Dhammaan meelaha buuxi.", "error")
        elif Student.query.filter_by(student_code=code).first():
            flash("Student ID-gaas horay ayuu u jiraa.", "error")
        else:
            db.session.add(
                Student(
                    student_code=code,
                    full_name=name,
                    class_name=class_name
                )
            )
            db.session.commit()
            flash("Ardayga waa la diiwaangeliyey.", "success")

        return redirect(url_for("students"))

    records = Student.query.order_by(
        Student.class_name, Student.full_name
    ).all()
    return render_template("students.html", students=records)


@app.route("/users", methods=["GET", "POST"])
@admin_required
def users():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "teacher")

        if role not in ("admin", "teacher"):
            role = "teacher"

        if not username or len(password) < 8:
            flash("Geli username iyo password ugu yaraan 8 xaraf.", "error")
        elif User.query.filter_by(username=username).first():
            flash("Username-kan horay ayuu u jiraa.", "error")
        else:
            user = User(username=username, role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("User-ka waa la sameeyey.", "success")

        return redirect(url_for("users"))

    return render_template(
        "users.html",
        users=User.query.order_by(User.username).all()
    )


@app.route("/timetable", methods=["GET", "POST"])
@admin_required
def timetable():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        start = request.form.get("start_time", "")
        end = request.form.get("end_time", "")
        weekday = request.form.get("weekday", "0")

        try:
            start_time = time.fromisoformat(start)
            end_time = time.fromisoformat(end)
            day = int(weekday)

            if not name or end_time <= start_time or day not in range(0, 6):
                raise ValueError()

            db.session.add(
                Period(
                    name=name,
                    start_time=start_time,
                    end_time=end_time,
                    weekday=day
                )
            )
            db.session.commit()
            flash("Xiisadda waa la kaydiyey.", "success")

        except ValueError:
            flash(
                "Hubi magaca, waqtiga, iyo maalinta. "
                "Dhammaadku waa inuu ka dambeeyaa bilowga.",
                "error"
            )

        return redirect(url_for("timetable"))

    periods = Period.query.order_by(
        Period.weekday, Period.start_time
    ).all()
    return render_template("timetable.html", periods=periods)


@app.route("/attendance", methods=["GET", "POST"])
@login_required
def attendance():
    today = datetime.now(SOMALIA_TZ).date()
    selected_class = request.values.get("class_name", "").strip()
    selected_period_id = request.values.get("period_id", type=int)
    selected_date = request.values.get(
        "attendance_date", today.isoformat()
    )

    try:
        day = date.fromisoformat(selected_date)
    except (ValueError, TypeError):
        day = today
        selected_date = day.isoformat()

    periods = Period.query.order_by(Period.start_time).all()
    classes = [
        row[0]
        for row in (
            db.session.query(Student.class_name)
            .filter_by(active=True)
            .distinct()
            .order_by(Student.class_name)
            .all()
        )
    ]

    period = (
        db.session.get(Period, selected_period_id)
        if selected_period_id
        else current_period()
    )

    if selected_class and selected_class not in classes:
        flash("Fasalka la doortay ma jiro.", "error")
        return redirect(url_for("attendance"))

    students_list = []
    if selected_class:
        students_list = (
            Student.query
            .filter_by(class_name=selected_class, active=True)
            .order_by(Student.full_name)
            .all()
        )

    existing = {}
    if period and students_list:
        student_ids = [student.id for student in students_list]
        records = Attendance.query.filter(
            Attendance.period_id == period.id,
            Attendance.attendance_date == day,
            Attendance.student_id.in_(student_ids)
        ).all()
        existing = {record.student_id: record.status for record in records}

    is_admin = current_user.role == "admin"

    if request.method == "POST":
        if not selected_class:
            flash("Marka hore dooro fasal.", "error")
            return redirect(url_for("attendance"))

        if not period:
            flash("Dooro xiisad sax ah. Hubi jadwalka xiisadaha.", "error")
            return redirect(url_for(
                "attendance",
                class_name=selected_class,
                attendance_date=selected_date
            ))

        if not students_list:
            flash("Fasalkan arday firfircoon kuma jiraan.", "error")
            return redirect(url_for(
                "attendance",
                class_name=selected_class,
                period_id=period.id,
                attendance_date=selected_date
            ))

        # Existing records are editable only by Admin.
        if existing and not is_admin:
            flash(
                "Xaadirinta taariikhdan hore ayay u kaydsan tahay. "
                "Admin keliya ayaa wax ka beddeli kara.",
                "error"
            )
            return redirect(url_for(
                "attendance",
                class_name=selected_class,
                period_id=period.id,
                attendance_date=selected_date
            ))

        valid_statuses = {"Present", "Absent", "Late", "Excused"}
        now = datetime.now(SOMALIA_TZ).replace(tzinfo=None)

        try:
            for student in students_list:
                status = request.form.get(
                    f"status_{student.id}", "Present"
                )
                if status not in valid_statuses:
                    status = "Present"

                record = Attendance.query.filter_by(
                    student_id=student.id,
                    period_id=period.id,
                    attendance_date=day
                ).first()

                if record:
                    # Update existing record instead of inserting a duplicate.
                    record.status = status
                    record.marked_by = current_user.id
                    record.marked_at = now
                else:
                    db.session.add(
                        Attendance(
                            student_id=student.id,
                            period_id=period.id,
                            attendance_date=day,
                            status=status,
                            marked_by=current_user.id,
                            marked_at=now
                        )
                    )

            db.session.commit()
            flash(
                "Xaadirinta waa la kaydiyey/cusboonaysiiyey.",
                "success"
            )

        except Exception:
            db.session.rollback()
            app.logger.exception("Attendance save failed")
            flash(
                "Kaydintu way fashilantay. Fadlan mar kale isku day.",
                "error"
            )

        return redirect(url_for(
            "attendance",
            class_name=selected_class,
            period_id=period.id,
            attendance_date=selected_date
        ))

    return render_template(
        "attendance.html",
        school_name=SCHOOL_NAME,
        students=students_list,
        classes=classes,
        periods=periods,
        selected_class=selected_class,
        selected_period=period,
        selected_date=selected_date,
        existing=existing,
        active_period=current_period(),
        is_admin=is_admin
    )


@app.route("/reports")
@login_required
def reports():
    date_text = request.args.get(
        "date", datetime.now(SOMALIA_TZ).date().isoformat()
    )
    class_name = request.args.get("class_name", "").strip()

    try:
        day = date.fromisoformat(date_text)
    except ValueError:
        day = datetime.now(SOMALIA_TZ).date()
        date_text = day.isoformat()

    query = Attendance.query.filter_by(attendance_date=day)
    if class_name:
        query = query.join(Student).filter(Student.class_name == class_name)

    records = query.order_by(
        Attendance.period_id, Attendance.student_id
    ).all()

    classes = [
        row[0]
        for row in (
            db.session.query(Student.class_name)
            .distinct()
            .order_by(Student.class_name)
            .all()
        )
    ]

    counts = {
        status: sum(1 for record in records if record.status == status)
        for status in ("Present", "Absent", "Late", "Excused")
    }

    return render_template(
        "reports.html",
        records=records,
        classes=classes,
        class_name=class_name,
        date_text=date_text,
        counts=counts
    )


@app.route("/health")
def health():
    return {"status": "ok", "app": SCHOOL_NAME}


with app.app_context():
    db.create_all()

    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("ADMIN_PASSWORD")

    if not User.query.filter_by(username=admin_username).first():
        if not admin_password:
            # Set ADMIN_PASSWORD in the deployment environment before production.
            admin_password = "ChangeMe123!"

        admin = User(username=admin_username, role="admin")
        admin.set_password(admin_password)
        db.session.add(admin)
        db.session.commit()


if __name__ == "__main__":
    app.run(
        debug=False,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000"))
    )
