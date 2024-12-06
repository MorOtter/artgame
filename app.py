from flask import Flask, render_template, request, jsonify, abort, url_for
import random
import os
import sqlite3
import logging
from flask_cors import CORS

app = Flask(__name__, template_folder='Templates')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define directories for human and AI images (use lowercase "static" to match Flask convention)
HUMAN_DIR = "static/Human"
AI_DIR = "static/AI"

# Function to list images in the directory, with fallback to an empty list
def get_image_list(directory):
    try:
        return [f for f in os.listdir(directory) if f.endswith(('.png', '.jpg', '.jpeg'))]
    except FileNotFoundError:
        logging.warning(f"Directory '{directory}' not found.")
        return []

# Get images
Human_images = get_image_list(HUMAN_DIR)
AI_images = get_image_list(AI_DIR)

DATABASE = 'database.db'  # Path for the SQLite database file

# Database connection function
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Initialize the database
def init_db():
    with get_db_connection() as conn:
        # Create scores table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                score INTEGER NOT NULL
            );
        ''')
        
        # Create image stats table to track votes and favorite counts
        conn.execute('''
            CREATE TABLE IF NOT EXISTS image_stats (
                image TEXT PRIMARY KEY,
                AI_votes INTEGER DEFAULT 0,
                Human_votes INTEGER DEFAULT 0,
                favorite_count INTEGER DEFAULT 0
            );
        ''')

        # Populate image stats table with images if not already present
        images = Human_images + AI_images
        for image in images:
            conn.execute('''
                INSERT OR IGNORE INTO image_stats (image, AI_votes, Human_votes, favorite_count)
                VALUES (?, 0, 0, 0)
            ''', (image,))

CORS(app)  # This will enable CORS for all routes

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/quiz")
def quiz():
    try:
        # Get updated lists of images
        Human_images = get_image_list(HUMAN_DIR)
        AI_images = get_image_list(AI_DIR)

        # Log the retrieved images
        logging.info(f"Human images: {Human_images}")
        logging.info(f"AI images: {AI_images}")

        # Combine the images
        images = Human_images + AI_images

        # If there are no images, provide a fallback message and return empty results
        if not images:
            logging.warning("No images available for the quiz. Returning fallback response.")
            return render_template("index.html", images=[])

        # Randomly sample images
        sampled_images = random.sample(images, min(10, len(images)))  # Sample up to 10 images

        # Generate the correct paths for images using `url_for`
        sampled_images_with_paths = [
            url_for('static', filename=f"{'Human' if 'Human' in img else 'AI'}/{img}") for img in sampled_images
        ]

        return render_template("index.html", images=sampled_images_with_paths)
    except Exception as e:
        logging.error(f"Error in quiz route: {e}")
        return jsonify({"error": "An error occurred while loading the quiz."}), 500

@app.route("/gallery")
def gallery():
    with get_db_connection() as conn:
        # Sort images by favorite count in descending order (most popular first)
        image_stats = conn.execute('''
            SELECT * FROM image_stats
            ORDER BY favorite_count DESC
        ''').fetchall()
    
    # Debugging print to verify data
    logging.info(f"Image Stats Data Retrieved: {image_stats}")

    return render_template("gallery.html", image_stats=image_stats)

def validate_votes(votes):
    """Validate the votes input."""
    if not isinstance(votes, list) or len(votes) != 10:
        abort(400, description="You must make a selection for all 10 images.")
    for vote in votes:
        if 'image' not in vote or 'is_AI' not in vote:
            abort(400, description="Each vote must contain 'image' and 'is_AI' fields.")

def update_votes(conn, votes):
    """Update the vote counts in the database and return the correct score."""
    correct = 0
    for vote in votes:
        image = vote["image"]
        guessed_AI = vote["is_AI"]
        is_ai = "AI/" in image

        if guessed_AI == is_ai:
            correct += 1

        # Update image stats in the database
        if guessed_AI:
            conn.execute('UPDATE image_stats SET AI_votes = AI_votes + 1 WHERE image = ?', (image,))
        else:
            conn.execute('UPDATE image_stats SET Human_votes = Human_votes + 1 WHERE image = ?', (image,))
    return correct

def save_favorite_and_score(conn, favorite, name, score):
    """Update the favorite count and save the player's score."""
    conn.execute('UPDATE image_stats SET favorite_count = favorite_count + 1 WHERE image = ?', (favorite,))
    conn.execute('INSERT INTO scores (name, score) VALUES (?, ?)', (name, score))

@app.route("/submit", methods=["POST"])
def submit():
    """Handle the submission of votes and update the database."""
    data = request.json
    votes = data.get("votes", [])
    favorite = data.get("favorite")
    name = data.get("name")

    # Validate input
    validate_votes(votes)

    with get_db_connection() as conn:
        try:
            correct = update_votes(conn, votes)
            save_favorite_and_score(conn, favorite, name, correct)
            conn.commit()  # Commit the changes to the database
        except Exception as e:
            logging.error(f"Error during submit operation: {e}")
            abort(500, description="An error occurred while processing your submission.")

    return jsonify({"score": correct}), 200

@app.route("/leaderboard")
def leaderboard():
    page = int(request.args.get('page', 1))  # Default to page 1 if not specified
    page_size = 10
    offset = (page - 1) * page_size

    with get_db_connection() as conn:
        leaderboard_data = conn.execute('''
            SELECT name, score FROM scores
            ORDER BY score DESC, id ASC
            LIMIT ? OFFSET ?
        ''', (page_size, offset)).fetchall()

    return render_template("leaderboard.html", leaderboard=leaderboard_data, current_page=page)

if __name__ == "__main__":
    # Initialize the database before running the app
    init_db()
    app.run(debug=True)
