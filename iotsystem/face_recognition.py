import cv2
import numpy as np
import face_recognition
import os
import requests
import time
import logging
import serial

# Import the Firebase Attendance System
from firebase import AttendanceSystemSchema, setup_firebase

class FaceRecognitionApp:
    def __init__(self, known_faces_dir='known_faces', esp32_cam_ip='192.168.100.6', serial_port='COM3', baud_rate=115200):
        """
        Initialize the Face Recognition Application
        """
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger('FaceRecognitionApp')

        self.known_faces_dir = known_faces_dir
        self.esp32_cam_ip = esp32_cam_ip

        # Initialize serial connection
        try:
            self.serial_connection = serial.Serial(serial_port, baud_rate, timeout=1)
            self.logger.info(f"Serial connection established on {serial_port}")
        except Exception as e:
            self.logger.error(f"Failed to establish serial connection: {e}")
            self.serial_connection = None

        # Load known faces
        self.known_face_encodings = []
        self.known_face_names = []

        # Firebase setup
        self.firebase_db = setup_firebase()
        if self.firebase_db is None:
            self.logger.error("Failed to connect to Firebase")
            raise Exception("Firebase connection failed")

        self.load_known_faces()

    def load_known_faces(self):
        """
        Load known faces from the specified directory
        """
        try:
            known_faces_count = 0
            for filename in os.listdir(self.known_faces_dir):
                if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                    image_path = os.path.join(self.known_faces_dir, filename)

                    try:
                        # Load the image
                        face_image = face_recognition.load_image_file(image_path)

                        # Find face encodings
                        face_encodings = face_recognition.face_encodings(face_image)

                        if len(face_encodings) > 0:
                            # Take the first face encoding
                            face_encoding = face_encodings[0]

                            # Use filename (without extension) as the student ID
                            student_id = os.path.splitext(filename)[0]

                            self.known_face_encodings.append(face_encoding)
                            self.known_face_names.append(student_id)

                            known_faces_count += 1

                    except Exception as e:
                        self.logger.error(f"Error processing {filename}: {e}")

            self.logger.info(f"Loaded {known_faces_count} known faces")

        except Exception as e:
            self.logger.error(f"Error loading known faces: {e}")

    def capture_from_esp32cam(self):
        """
        Capture an image from the ESP32-CAM
        """
        try:
            # Construct the URL to capture image from ESP32-CAM
            capture_url = f'http://{self.esp32_cam_ip}/capture'

            response = requests.get(capture_url, timeout=10)

            if response.status_code == 200:
                # Convert the response content to a numpy array
                nparr = np.frombuffer(response.content, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                return frame
            else:
                self.logger.error("Failed to capture image from ESP32-CAM")
                return None

        except Exception as e:
            self.logger.error(f"Error capturing from ESP32-CAM: {e}")
            return None

    def trigger_led_blink(self):
        """
        Trigger the LED blink on ESP32-CAM using serial communication
        """
        try:
            if self.serial_connection and self.serial_connection.is_open:
                self.logger.info("Sending blink command to ESP32-CAM")
                self.serial_connection.write(b'blink\n')
                time.sleep(0.1)  # Wait briefly for the command to be processed
                return True
            else:
                self.logger.error("Serial connection not available")
                return False
        except Exception as e:
            self.logger.error(f"Error triggering LED: {e}")
            return False

    def recognize_faces(self, frame):
        """
        Recognize faces in the given frame and mark attendance
        """
        try:
            if frame is None:
                return frame

            # Convert the image from BGR (OpenCV) to RGB (face_recognition)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Find all face locations and face encodings in the current frame
            face_locations = face_recognition.face_locations(rgb_frame)
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                # Compare face encodings
                matches = face_recognition.compare_faces(
                    self.known_face_encodings,
                    face_encoding,
                    tolerance=0.5
                )

                name = "Unknown"
                color = (0, 0, 255)  # Red for unknown faces

                if True in matches:
                    first_match_index = matches.index(True)
                    student_id = self.known_face_names[first_match_index]
                    name = student_id
                    color = (0, 255, 0)  # Green for known faces

                    try:
                        attendance_result = AttendanceSystemSchema.mark_attendance(student_id)
                        if attendance_result:
                            self.logger.info(f"Attendance marked for student {student_id}")
                            if self.trigger_led_blink():
                                self.logger.info("LED blink confirmed")
                            else:
                                self.logger.error("Failed to trigger LED")
                    except Exception as e:
                        self.logger.error(f"Error marking attendance: {e}")

                # Draw rectangle and name on the frame
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.putText(frame, name, (left + 6, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)

            return frame

        except Exception as e:
            self.logger.error(f"Error in face recognition: {e}")
            return frame

    def run(self):
        """
        Main application loop
        """
        self.logger.info("Face Recognition App Started. Press 'q' to quit.")

        try:
            while True:
                # Capture frame from ESP32-CAM
                frame = self.capture_from_esp32cam()

                if frame is not None:
                    # Recognize faces and mark attendance
                    annotated_frame = self.recognize_faces(frame)

                    # Display the result
                    cv2.imshow('ESP32-CAM Face Recognition', annotated_frame)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

                time.sleep(0.5)

        except KeyboardInterrupt:
            self.logger.info("Application stopped by user")

        finally:
            cv2.destroyAllWindows()
            if hasattr(self, 'serial_connection') and self.serial_connection:
                self.serial_connection.close()

    def __del__(self):
        if hasattr(self, 'serial_connection') and self.serial_connection:
            self.serial_connection.close()

if __name__ == "__main__":
    app = FaceRecognitionApp()
    app.run()
