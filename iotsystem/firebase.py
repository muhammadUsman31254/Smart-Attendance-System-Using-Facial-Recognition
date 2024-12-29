import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime, timedelta

def setup_firebase(cred_path='smart-attendance-system-d6ed0-firebase-adminsdk-6amex-6984706823.json'):
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(
                cred, 
                {'databaseURL': 'https://smart-attendance-system-d6ed0-default-rtdb.firebaseio.com/'}
            )
            print("Firebase Realtime Database connected successfully")
        return db
    except Exception as e:
        print(f"Firebase connection error: {e}")
        return None

# Global database reference
firebase_db = setup_firebase()

class AttendanceSystemSchema:
    @staticmethod
    def create_student(student_id, name, email):
        student_data = {
            'student_id': student_id,
            'name': name,
            'email': email,
            'enrolled_courses': []
        }
        
        # Store student in Realtime Database under a generated key
        students_ref = firebase_db.reference('students')
        new_student_ref = students_ref.push()
        new_student_ref.set(student_data)
        return student_data
    
    @staticmethod
    def create_course(course_id, course_name, instructor_name, schedule):
        course_data = {
            'course_id': course_id,
            'name': course_name,
            'instructor': instructor_name,
            'enrolled_students': [],
            'schedule': schedule  # Schedule is now part of course data
        }
        
        # Store course in Realtime Database under a generated key
        courses_ref = firebase_db.reference('courses')
        new_course_ref = courses_ref.push()
        new_course_ref.set(course_data)
        return course_data
    
    @staticmethod
    def enroll_student_to_course(student_id, course_id):
        # Find student and course by their IDs
        students_ref = firebase_db.reference('students')
        courses_ref = firebase_db.reference('courses')
        
        # Query to find student and course
        student_query = students_ref.order_by_child('student_id').equal_to(student_id).get()
        course_query = courses_ref.order_by_child('course_id').equal_to(course_id).get()
        
        if not student_query or not course_query:
            print("Student or course not found")
            return
        
        # Get the first (and should be only) matching student and course
        student_key = list(student_query.keys())[0]
        course_key = list(course_query.keys())[0]
        
        # Update student's enrolled courses
        student_courses = student_query[student_key].get('enrolled_courses', [])
        if course_id not in student_courses:
            student_courses.append(course_id)
            students_ref.child(student_key).child('enrolled_courses').set(student_courses)
        
        # Update course's enrolled students
        course_students = course_query[course_key].get('enrolled_students', [])
        if student_id not in course_students:
            course_students.append(student_id)
            courses_ref.child(course_key).child('enrolled_students').set(course_students)
    
    @staticmethod
    def find_current_course(student_id, timestamp=None):
        if timestamp is None:
            timestamp = datetime.now()
        
        # Find student by student_id
        students_ref = firebase_db.reference('students')
        student_query = students_ref.order_by_child('student_id').equal_to(student_id).get()
        
        if not student_query:
            return None
        
        # Get enrolled courses
        student_data = list(student_query.values())[0]
        enrolled_courses = student_data.get('enrolled_courses', [])
        
        # Get the day of the week
        day = timestamp.strftime('%A')
        
        # Query all courses
        courses_ref = firebase_db.reference('courses')
        all_courses = courses_ref.get()
        
        # Check each course
        for course_key, course_data in all_courses.items():
            if course_data['course_id'] not in enrolled_courses:
                continue
                
            schedule = course_data.get('schedule', {})
            if day not in schedule:
                continue
                
            class_time = schedule[day]
            class_start = datetime.strptime(class_time['start_time'], '%H:%M').time()
            class_end = datetime.strptime(class_time['end_time'], '%H:%M').time()
            
            class_start_datetime = datetime.combine(timestamp.date(), class_start)
            class_end_datetime = datetime.combine(timestamp.date(), class_end)
            
            if class_start_datetime <= timestamp <= (class_end_datetime + timedelta(minutes=15)):
                return course_data['course_id']
        
        return None
    
    @staticmethod
    def mark_attendance(student_id, timestamp=None):
        if timestamp is None:
            timestamp = datetime.now()
        
        course_id = AttendanceSystemSchema.find_current_course(student_id, timestamp)
        
        if not course_id:
            print(f"No active course found for student {student_id} at {timestamp}")
            return False
        
        # Check existing attendance
        attendance_ref = firebase_db.reference('attendance')
        existing_query = attendance_ref.order_by_child('student_id').equal_to(student_id).get()
        
        if existing_query:
            for record in existing_query.values():
                if (record.get('course_id') == course_id and 
                    record.get('date') == timestamp.date().isoformat()):
                    print(f"Attendance already marked for student {student_id} in course {course_id} on {timestamp.date()}")
                    return False
        
        attendance_data = {
            'course_id': course_id,
            'student_id': student_id,
            'date': timestamp.date().isoformat(),
            'timestamp': timestamp.isoformat(),
            'status': 'present'
        }
        
        new_attendance_ref = attendance_ref.push()
        new_attendance_ref.set(attendance_data)
        
        print(f"Attendance marked for student {student_id} in course {course_id}")
        return True

def main():
    if firebase_db is None:
        print("Failed to connect to Firebase. Exiting.")
        return
    
    try:
        # # Create student
        # AttendanceSystemSchema.create_student(
        #     '000004', 
        #     'Obaid Sajjad', 
        #     'hilmand.atk@gmail.com'
        # )
        
        # # Create course with schedule included
        # schedule = {
        #     'Sunday': {'start_time': '12:00', 'end_time': '13:00'}
        # }
        # AttendanceSystemSchema.create_course(
        #     'CSE002', 
        #     'Technical Writing', 
        #     'Dr. Ameer Sultan',
        #     schedule
        # )
        
        # Enroll student to course
        AttendanceSystemSchema.enroll_student_to_course('000004', 'CSE002')
        
        # # Mark attendance
        # AttendanceSystemSchema.mark_attendance('000003')
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    main()