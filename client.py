"""""""""
import base64
import cv2
import time
import threading
import socketio


def send_frame(sio, client_id, camera_id, frame):
    _, buffer = cv2.imencode('.jpg', frame)
    encoded_image = base64.b64encode(buffer).decode('utf-8')
    sio.emit('video_frame', {'client_id': client_id, 'camera_id': camera_id, 'image': encoded_image})


def camera_thread(sio, client_id, camera_id, camera_source):
    cap = cv2.VideoCapture(camera_source)

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        resized_frame = cv2.resize(frame, (640, 480))
        send_frame(sio, client_id, camera_id, resized_frame)
        time.sleep(0.01)

    cap.release()


if __name__ == "__main__":
    sio = socketio.Client()

    client_id = '1'  # Replace this with the actual client_id

    def on_connect():
        sio.emit('register_client_id', client_id)

    sio.on('connect', on_connect)
    sio.connect('http://localhost:80')

    camera_sources = [0, 1]  # Add more camera sources if needed
    threads = []

    for i, camera_source in enumerate(camera_sources):
        t = threading.Thread(target=camera_thread, args=(sio, client_id, i, camera_source))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()
"""""

import base64
import cv2
import time
import threading
import socketio
from socketio import exceptions


def frame_to_base64(frame):
    _, buffer = cv2.imencode('.jpg', frame)
    return base64.b64encode(buffer).decode('utf-8')


def send_frame(sio, client_id, camera_id, frame):
    encoded_image = frame_to_base64(frame)
    try:
        sio.emit('video_frame', {'client_id': client_id, 'camera_id': camera_id, 'image': encoded_image})
    except exceptions.BadNamespaceError as e:
        print(f"Error: {e}. Retrying to connect...")
        sio.connect('http://0.0.0.0:80')
        sio.emit('register_client_id', client_id)
        sio.emit('video_frame', {'client_id': client_id, 'camera_id': camera_id, 'image': encoded_image})


def camera_thread(sio, client_id, camera_id, camera_source):
    cap = cv2.VideoCapture(camera_source)

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        resized_frame = cv2.resize(frame, (640, 480))
        send_frame(sio, client_id, camera_id, resized_frame)
        time.sleep(0.01)

    cap.release()


def main():
    sio = socketio.Client()

    def on_connect():
        sio.emit('register_client_id', client_id)

    sio.on('connect', on_connect)

    client_id = '1'  # Replace this with the actual client_id

    try:
        sio.connect('http://0.0.0.0:80')
    except (socketio.exceptions.ConnectionError, socketio.exceptions.ConnectionRefusedError) as e:
        print(f"Error: {e}. Could not connect to the server.")
        return

    camera_sources = [0, 1, 2, 3]  # Add more camera sources if needed
    threads = []

    for i, camera_source in enumerate(camera_sources):
        t = threading.Thread(target=camera_thread, args=(sio, client_id, i, camera_source))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()


if __name__ == "__main__":
    main()

