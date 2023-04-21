
import cv2
import cvzone
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'face_recognition_models'))
import face_recognition

classNames = []
classFile = 'models/coco.names'

with open(classFile, 'rt') as f:
    classNames = f.read().split('\n')

configPath = 'models/ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt'
weightsPath = "models/frozen_inference_graph.pb"

net = cv2.dnn_DetectionModel(weightsPath, configPath)
net.setInputSize(320, 320)
net.setInputScale(1.0 / 127.5)
net.setInputMean((127.5, 127.5, 127.5))
net.setInputSwapRB(True)


def detect_objects(frame, thres=0.5, nmsThres=0.3):
    classIds, confs, bbox = net.detect(frame, confThreshold=thres, nmsThreshold=nmsThres)

    if classIds is not None:
        for classId, conf, box in zip(classIds, confs, bbox):
            cvzone.cornerRect(frame, box)
            cv2.putText(frame, f'{classNames[classId - 1].upper()} {round(conf * 100, 2)}',
                        (box[0] + 10, box[1] + 30), cv2.FONT_HERSHEY_COMPLEX_SMALL,
                        1, (0, 255, 0), 2)

    return frame


# Face recognition code
# Load known images of persons and assign names
known_person_dir = "profile_images/persons"
known_face_encodings = []
known_person_names = []
ageProto = "models/age_deploy.prototxt"
ageModel = "models/age_net.caffemodel"
genderProto = "models/gender_deploy.prototxt"
genderModel = "models/gender_net.caffemodel"
MODEL_MEAN_VALUES = (78.4263377603, 87.7689143744, 114.895847746)
ageList = ['(0-2)', '(4-6)', '(8-12)', '(15-20)', '(25-32)', '(38-43)', '(48-53)', '(60-100)']
genderList = ['Male', 'Female']
ageNet = cv2.dnn.readNet(ageModel, ageProto)
genderNet = cv2.dnn.readNet(genderModel, genderProto)

face_cascade = cv2.CascadeClassifier("haarcascade_frontalface_alt2.xml")
ds_factor = 0.6

for person_image in os.listdir(known_person_dir):
    image_path = os.path.join(known_person_dir, person_image)
    image = face_recognition.load_image_file(image_path)
    face_encoding = face_recognition.face_encodings(image)[0]

    known_face_encodings.append(face_encoding)
    known_person_names.append(os.path.splitext(person_image)[0])

# Load the Haar Cascade classifier for face detection
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def detect_faces(frame):
    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30),
                                          flags=cv2.CASCADE_SCALE_IMAGE)
    blob = cv2.dnn.blobFromImage(frame, 1.0, (227, 227), MODEL_MEAN_VALUES, swapRB=False)
    genderNet.setInput(blob)
    genderPreds = genderNet.forward()
    gender = genderList[genderPreds[0].argmax()]
    ageNet.setInput(blob)
    agePreds = ageNet.forward()
    age = ageList[agePreds[0].argmax()]

    for (x, y, w, h) in faces:
        top, right, bottom, left = y, x + w, y + h, x

        # Extract the face from the RGB frame
        face_rgb = frame[top:bottom, left:right]
        face_rgb = cv2.cvtColor(face_rgb, cv2.COLOR_BGR2RGB)

        # Encode the face
        unknown_face_encodings = face_recognition.face_encodings(face_rgb)

        if unknown_face_encodings:
            results = face_recognition.compare_faces(known_face_encodings, unknown_face_encodings[0])

            name = "Unknown"
            color = (0, 0, 255)  # Red
            if True in results:
                font = cv2.FONT_HERSHEY_DUPLEX
                matched_index = results.index(True)
                name = known_person_names[matched_index]
                color = (0, 255, 0)  # Green
                # Draw a rectangle around the face
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.putText(frame, name, (x + 10, y - 30), font, 1, (0, 255, 0), 3,
                            cv2.LINE_AA)
            else:
                # Draw a rectangle around the face
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)

                # Draw a label with the name below the face
                cv2.rectangle(frame, (left, bottom), (right, bottom), color, cv2.FILLED)
                font = cv2.FONT_HERSHEY_DUPLEX
                cv2.putText(frame, name, (x + 10, y - 70), font, 1, color, 3,
                            cv2.LINE_AA)
                cv2.putText(frame, f'{gender}', (x + 10, y - 40), font, 1, (0, 0, 255), 3, cv2.LINE_AA)
                cv2.putText(frame, f'{age}', (x + 10, y - 10), font, 1, (0, 0, 255), 3, cv2.LINE_AA)

    return frame
