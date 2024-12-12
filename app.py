from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, make_response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from weasyprint import HTML
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shifts.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# User model to manage multiple users
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    shifts = db.relationship('Shift', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.name}>'

# Shift model to store shift data
class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    break_time = db.Column(db.Integer, nullable=False)  # break in minutes
    total_time = db.Column(db.Integer, nullable=False)  # total working hours in minutes
    description = db.Column(db.String(200), nullable=True)  # optional description
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # ForeignKey for user

    def __init__(self, start_time, end_time, break_time, user_id, description=None):
        self.start_time = start_time
        self.end_time = end_time
        self.break_time = break_time
        self.user_id = user_id
        self.description = description
        self.total_time = (end_time - start_time).seconds // 60 - break_time  # Adjust total hours by break time

    def formatted_start_time(self):
        return self.start_time.strftime('%d-%m-%Y %H:%M')

    def formatted_end_time(self):
        return self.end_time.strftime('%d-%m-%Y %H:%M')

    def formatted_total_time(self):
        hours = self.total_time // 60
        minutes = self.total_time % 60
        return f'{hours}h {minutes}m'


@app.route('/')
def index():
    shifts = Shift.query.all()
    users = User.query.all()

    # Get the current month and year
    today = datetime.today()
    current_month = today.strftime('%B %Y')  # Current month and year (e.g., 'January 2024')
    
    # Prepare the calendar data for this month
    start_date = today.replace(day=1)  # Start of the current month
    end_date = (start_date + timedelta(days=31)).replace(day=1)  # Start of the next month

    calendar_days = []
    day = start_date
    while day < end_date:
        shifts_for_day = [shift for shift in shifts if shift.start_time.date() == day.date()]
        calendar_days.append({
            'date': day.day,
            'shifts': shifts_for_day
        })
        day += timedelta(days=1)

    return render_template('index.html', shifts=shifts, users=users, current_month=current_month, calendar_days=calendar_days)


@app.route('/shift_management', methods=['GET', 'POST'])
def shift_management():
    users = User.query.all()
    shifts = Shift.query.all()

    if request.method == 'POST':
        # Add new shift
        start_time = datetime.strptime(request.form['start_time'], '%d-%m-%Y %H:%M')
        end_time = datetime.strptime(request.form['end_time'], '%d-%m-%Y %H:%M')
        break_time = int(request.form['break_time'])
        user_id = int(request.form['user_id'])
        description = request.form.get('description')

        new_shift = Shift(start_time=start_time, end_time=end_time, break_time=break_time, user_id=user_id, description=description)
        db.session.add(new_shift)
        db.session.commit()

        return redirect(url_for('shift_management'))

    return render_template('shift_management.html', shifts=shifts, users=users)


@app.route('/delete_shift/<int:shift_id>', methods=['POST'])
def delete_shift(shift_id):
    shift = Shift.query.get_or_404(shift_id)  # Find the shift by ID
    db.session.delete(shift)  # Delete the shift from the session
    db.session.commit()  # Commit the transaction
    return redirect(url_for('report'))  # Redirect to the report page after deletion


@app.route('/manage_users', methods=['GET', 'POST'])
def manage_users():
    if request.method == 'POST':
        name = request.form['name']
        new_user = User(name=name)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('manage_users'))
    
    users = User.query.all()
    return render_template('manage_users.html', users=users)

@app.route('/delete_user/<int:user_id>')
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # Delete all shifts associated with the user
    for shift in user.shifts:
        db.session.delete(shift)
    
    # Now delete the user
    db.session.delete(user)
    db.session.commit()
    
    return redirect(url_for('manage_users'))


@app.route('/report', methods=['GET', 'POST'])
def report():
    # Get the user_id, month, and year from the query string
    user_id = request.args.get('user_id')
    month = request.args.get('month', default=None, type=int)  # Get the month parameter as integer
    year = request.args.get('year', default=None, type=int)  # Get the year parameter as integer

    # Get the current year and month
    current_year = datetime.now().year
    current_month = datetime.now().month

    # If no year is provided, default to the current year
    if not year:
        year = current_year

    # If no month is provided, default to the current month
    if not month:
        month = current_month

    # Generate the year range (from 5 years ago to 1 year in the future)
    year_range = list(range(current_year - 5, current_year + 2))

    # Start the query
    shifts_query = Shift.query

    # Filter by user if user_id is provided
    if user_id:
        shifts_query = shifts_query.filter_by(user_id=user_id)

    # Filter by month if month is provided (adjust for SQLite compatibility)
    if month:
        shifts_query = shifts_query.filter(func.strftime('%m', Shift.start_time) == f'{month:02d}')

    # Filter by year if year is provided (adjust for SQLite compatibility)
    if year:
        shifts_query = shifts_query.filter(func.strftime('%Y', Shift.start_time) == str(year))

    # Fetch all the filtered shifts and sort by start_time (ascending)
    shifts = shifts_query.order_by(Shift.start_time).all()

    # Group shifts by user
    users = User.query.all()  # Get all users to display in the report options
    shifts_by_user = {}
    for user in users:
        shifts_by_user[user] = [shift for shift in shifts if shift.user_id == user.id]

    # Calculate total worked hours for each user
    total_hours_by_user = {}
    for user, user_shifts in shifts_by_user.items():
        total_minutes = sum([shift.total_time for shift in user_shifts])
        total_hours = total_minutes // 60
        total_minutes_remaining = total_minutes % 60
        total_hours_by_user[user] = f"{total_hours}h {total_minutes_remaining}m"

    return render_template('report.html', shifts_by_user=shifts_by_user, total_hours_by_user=total_hours_by_user, users=users, year_range=year_range, current_month=current_month, current_year=current_year, month=month, year=year)



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
