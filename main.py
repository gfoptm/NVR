import base64
import datetime
import os
from base64 import decodebytes
from collections import defaultdict
from queue import Queue
from threading import Thread, Lock
from urllib.parse import urlparse
import cv2
import numpy as np
from flask import Flask, render_template, request, abort, redirect, url_for, jsonify
from flask import flash
from flask import send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from jinja2 import TemplateNotFound
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Email

from detection import detect_objects, detect_faces

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///user.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

socketio = SocketIO(app, async_mode='threading')

# Setup Flask-SQLAlchemy
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

UPLOAD_FOLDER = 'profile_images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/update_image', methods=['POST'])
@login_required
def update_image():
    if 'profile_image' not in request.files:
        flash('No file part')
        return redirect(request.url)
    file = request.files['profile_image']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        user_id = current_user.id
        relative_filepath = os.path.join(f'user_{user_id}', filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], relative_filepath)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        file.save(filepath)
        print(f"File saved at: {filepath}")  # Add this line for debugging

        current_user.profile_image = relative_filepath
        db.session.commit()

        print(f"User's profile_image: {current_user.profile_image}")  # Add this line for debugging

        flash('Profile image has been updated.')
        return redirect(url_for('profile'))
    else:
        flash('File type not allowed. Please upload a valid image file.')
        return redirect(request.url)


@app.route('/save_image', methods=['POST'])
def save_image():
    image_data = request.form['image_data']
    image_name = request.form['image_name']
    client_id = current_user.client_id

    header, encoded = image_data.split(",", 1)
    data = decodebytes(encoded.encode())

    # Use the user-provided image name and add a timestamp
    filename = secure_filename(f'{image_name}_id_{client_id}.jpg')

    persons_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'persons')
    os.makedirs(persons_folder, exist_ok=True)
    filepath = os.path.join(persons_folder, filename)

    with open(filepath, 'wb') as f:
        f.write(data)

    return jsonify(status='success')


@app.route('/view_image/<path:filename>')
def view_image(filename):
    persons_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'persons')
    return send_from_directory(persons_folder, filename)


@app.route('/face_images')
@login_required
def face_images():
    client_id = current_user.client_id
    persons_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'persons')
    all_image_files = os.listdir(persons_folder)

    # Check if the current user is an admin
    is_admin = current_user.is_admin

    if is_admin:
        # If the user is an admin, show all images
        image_files = all_image_files
    else:
        # If the user is not an admin, show only their images
        image_files = [img for img in all_image_files if f'_id_{client_id}.' in img]

    image_data = [{'url': url_for('view_image', filename=img), 'name': img} for img in image_files]
    users = User.query.order_by(User.username).all()
    profile_image_url = url_for('profile_image',
                                filename=current_user.profile_image) if current_user.profile_image else None

    return render_template('face_images.html', image_data=image_data, profile_image_url=profile_image_url, users=users)


@app.route('/delete_image', methods=['POST'])
@login_required
def delete_image():
    image_name = request.form['image_name']
    persons_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'persons')
    image_path = os.path.join(persons_folder, image_name)

    # Check if the file exists
    if os.path.exists(image_path):
        # Remove the file
        os.remove(image_path)
        return jsonify(status='success')
    else:
        return jsonify(status='error', message='File not found')


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True)
    address = db.Column(db.String(200))
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))
    phone_number = db.Column(db.String(20))
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    client_id = db.Column(db.String(64), nullable=True)  # Make sure it's nullable
    profile_image = db.Column(db.String(255), nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


with app.app_context():
    db.create_all()


def create_admin_if_not_exists(username, password, client_id):
    existing_admin = User.query.filter_by(username=username, is_admin=True).first()
    if existing_admin is None:
        admin = User(username=username, is_admin=True, client_id=client_id)
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()


with app.app_context():
    create_admin_if_not_exists('root', '_Nikiton098', 1)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        client_id = request.form['client_id']
        if 'role' in request.form:
            role = request.form['role']
        else:
            role = 'user'
        if not username or not password:
            flash("Registration failed: username and password are required", "warning")

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Registration failed: username already exists.", "warning")
        else:
            user = User(username=username, client_id=client_id)
            user.set_password(password)
            if role == 'admin':
                user.is_admin = True
            db.session.add(user)
            db.session.commit()
            return redirect(url_for('login'))
    return render_template('accounts/page-register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        client_id = request.form['client_id']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password) and user.client_id == client_id:
            login_user(user)
            return redirect(url_for('index', client_id=client_id))
        else:
            flash("Login Failed, Please try again.", "warning")
    return render_template('accounts/page-login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        if form.profile_image.data:
            filename = secure_filename(form.profile_image.data.filename)
            user_id = current_user.id
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], f'user_{user_id}', filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            form.profile_image.data.save(filepath)
            current_user.profile_image = filepath
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.address = form.address.data
        current_user.city = form.city.data
        current_user.country = form.country.data
        current_user.phone_number = form.phone_number.data
        current_user.set_password(form.password.data)
        db.session.commit()
        flash("Profile successfully updated.", "success")
        return redirect(url_for('profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.address.data = current_user.address
        form.city.data = current_user.city
        form.country.data = current_user.country
        form.phone_number.data = current_user.phone_number
        profile_image_url = url_for('profile_image',
                                    filename=current_user.profile_image) if current_user.profile_image else None
    return render_template('accounts/user-profile.html', form=form, profile_image_url=profile_image_url)


@app.route('/profile_image/<path:filename>', defaults={'user_id': None})
@app.route('/profile_image/<int:user_id>/<path:filename>')
@login_required
def profile_image(filename, user_id):
    if user_id is not None:
        user = User.query.get_or_404(user_id)
        if user.profile_image != filename:
            abort(404)
    return send_from_directory(directory=app.config['UPLOAD_FOLDER'], path=filename, as_attachment=False,
                               conditional=True)


@app.route('/admin/user_profile/<int:user_id>', methods=['GET'])
@login_required
def admin_user_profile(user_id):
    if not current_user.is_admin:
        abort(403)
    user = User.query.get_or_404(user_id)
    profile_image_url = url_for('profile_image',
                                filename=current_user.profile_image) if current_user.profile_image else None
    return render_template('admin/user_profile.html', user=user, profile_image_url=profile_image_url)


class EditProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    address = StringField('Address', validators=[DataRequired()])
    city = StringField('City', validators=[DataRequired()])
    country = StringField('Country', validators=[DataRequired()])
    phone_number = StringField('Phone Number', validators=[DataRequired()])
    password = PasswordField('New Password',
                             validators=[DataRequired(), EqualTo('confirm_password', message='Passwords must match')])
    confirm_password = PasswordField('Confirm New Password', validators=[DataRequired()])
    profile_image = FileField('Profile Image', validators=[FileAllowed(['jpg', 'jpeg', 'png'])])
    submit = SubmitField('Save Changes')


@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.address = form.address.data
        current_user.city = form.city.data
        current_user.country = form.country.data
        current_user.phone_number = form.phone_number.data
        current_user.set_password(form.password.data)
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.address.data = current_user.address
        form.city.data = current_user.city
        form.country.data = current_user.country
        form.phone_number.data = current_user.phone_number
    return render_template('edit_profile.html', form=form)


@app.route('/admin/clients')
@login_required
def admin_clients():
    if not current_user.is_admin:
        abort(403)
    users = User.query.order_by(User.username).all()
    profile_image_url = url_for('profile_image',
                                filename=current_user.profile_image) if current_user.profile_image else None
    return render_template('admin/tables.html', users=users, profile_image_url=profile_image_url)


@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        abort(403)

    user = User.query.get_or_404(user_id)
    if user.is_admin:
        flash("You cannot delete an admin user.", "warning")
        return redirect(url_for('admin_clients'))

    # Delete user's profile image if exists
    if user.profile_image:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], user.profile_image))
        except FileNotFoundError:
            pass

    db.session.delete(user)
    db.session.commit()

    flash(f"User {user.username} has been deleted.", "success")
    return redirect(url_for('admin_clients'))


camera_frames = {}
output_writers = {}
record_statuses = {}
video_folder = 'recordings'
last_saved_frames = {}

if not os.path.exists(video_folder):
    os.makedirs(video_folder)


@app.route('/')
@login_required
def index():
    client_id = current_user.client_id
    profile_image_url = url_for('profile_image',
                                filename=current_user.profile_image) if current_user.profile_image else None
    return render_template('home/index.html', client_id=client_id, profile_image_url=profile_image_url)


def get_segment(request):
    path = urlparse(request.url).path
    return path.split('/')[-1]


@app.route('/<template>')
@login_required
def route_template(template):
    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("home/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


@app.route('/get_client_id')
@login_required
def get_client_id():
    return {'client_id': current_user.client_id}


@app.route('/object_detection')
@login_required
def object_detection():
    return render_template('object_detection.html')


@app.route('/face_detection')
@login_required
def face_detection():
    return render_template('face_detection.html')


@app.route('/archive', methods=['GET', 'POST'])
@login_required
def archive():
    search_term = request.args.get('search', '')
    client_id = current_user.client_id
    users = User.query.order_by(User.username).all()
    profile_image_url = url_for('profile_image',
                                filename=current_user.profile_image) if current_user.profile_image else None

    if search_term:
        videos = [v for v in os.listdir(video_folder) if
                  search_term.lower() in v.lower() and f"client_{client_id}_" in v]
    else:
        videos = [v for v in os.listdir(video_folder) if f"client_{client_id}_" in v]

    return render_template('archive.html', videos=videos, search_term=search_term, profile_image_url=profile_image_url,
                           users=users)


@app.route('/video/<path:filename>')
@login_required
def video(filename):
    client_id = current_user.client_id
    if not f"client_{client_id}_" in filename:
        abort(403)
    return send_from_directory(directory=video_folder, path=filename, as_attachment=False, conditional=True)


def frame_to_base64(frame):
    _, buffer = cv2.imencode('.jpg', frame)
    frame_data = base64.b64encode(buffer).decode('utf-8')
    return frame_data


clients = defaultdict(list)


@socketio.on('register_client_id')
def handle_register_client_id(client_id):
    if current_user.is_authenticated and current_user.client_id == client_id:
        if request.sid not in clients[client_id]:
            clients[client_id].append(request.sid)


def write_video_frame(camera_id, frame):
    for key in record_statuses.keys():
        client_id, rec_camera_id = key
        if rec_camera_id == camera_id and record_statuses[key]:
            if key not in output_writers:
                fourcc = cv2.VideoWriter_fourcc(*'H264')
                filename = f"client_{client_id}_camera_{camera_id}_{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.mp4"
                output_path = os.path.join('recordings', filename)
                output_writers[key] = cv2.VideoWriter(output_path, fourcc, 20, (frame.shape[1], frame.shape[0]))
            output_writers[key].write(frame)
        elif key in output_writers and not record_statuses[key]:
            output_writers[key].release()
            del output_writers[key]


class CameraHandler:
    def __init__(self, skip_frames=1):
        self.frame_queues = defaultdict(Queue)
        self.frame_locks = defaultdict(Lock)
        self.processing_threads = {}
        self.skip_frames = skip_frames

    def add_frame(self, camera_id, client_id, frame):
        with self.frame_locks[camera_id]:
            self.frame_queues[camera_id].put((client_id, frame))
            if camera_id not in self.processing_threads or not self.processing_threads[camera_id].is_alive():
                self.processing_threads[camera_id] = Thread(target=self._process_frames, args=(camera_id,))
                self.processing_threads[camera_id].start()

    def _process_frames(self, camera_id):
        frame_count = 0
        while True:
            with self.frame_locks[camera_id]:
                if not self.frame_queues[camera_id].empty():
                    client_id, frame = self.frame_queues[camera_id].get()
                else:
                    break

            if frame_count % self.skip_frames == 0:
                object_frame = detect_objects(frame.copy())
                face_frame = detect_faces(frame.copy())

                # Send the video frame and processed frames to clients
                emit_data = {"camera_id": camera_id, "image": frame_to_base64(frame)}

                if object_frame is not None:
                    emit_data["object_image"] = frame_to_base64(object_frame)

                if face_frame is not None:
                    emit_data["face_image"] = frame_to_base64(face_frame)

                socketio.emit("video_frame", emit_data, room=clients[client_id])

                # Write video frame (if needed)
                write_video_frame(camera_id, frame)

                frame_count += 1


camera_handler = CameraHandler(skip_frames=2)  # You can change skip_frames.


@socketio.on('video_frame')
def handle_video_frame(json):
    camera_id = json['camera_id']
    image_data = json['image']
    sender_client_id = json['client_id']

    frame_data = base64.b64decode(image_data)
    frame_array = np.frombuffer(frame_data, dtype=np.uint8)
    frame = cv2.imdecode(frame_array, flags=cv2.IMREAD_COLOR)

    camera_handler.add_frame(camera_id, sender_client_id, frame)


@socketio.on('toggle_record')
def toggle_record(json):
    camera_id = json['camera_id']
    client_id = json['client_id'] if 'client_id' in json else 'anonymous'
    record_key = (client_id, camera_id)
    record_status = json['status']

    if record_key not in record_statuses:
        record_statuses[record_key] = False

    record_statuses[record_key] = record_status

    if not record_statuses[record_key] and record_key in output_writers:
        output_writers[record_key].release()
        del output_writers[record_key]


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=80, debug=True, allow_unsafe_werkzeug=True)
