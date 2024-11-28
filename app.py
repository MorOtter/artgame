from flask import Flask, render_template, request, jsonify
import random
import os
import sqlite3

app = Flask(__name__, template_folder='Templates')

# Define the directory for human images
HUMAN_DIR = "Static/Human/"

# Check if the directory exists
if not os.path.exists(HUMAN_DIR):
    print(f"Warning: The directory '{HUMAN_DIR}' does not exist.")
    Human_images = []  # Set to an empty list or handle as needed
else:
    # List images in the directory
    Human_images = [f"/Human/{img}" for img in os.listdir(HUMAN_DIR) if img.endswith(('.png', '.jpg', '.jpeg'))]

AI_DIR = "Static/AI/"
ai_images = [f"AI/{img}" for img in os.listdir(AI_DIR) if img.endswith(('.png', '.jpg', '.jpeg'))]

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


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/quiz")
def quiz():
    try:
        # Ensure that Human_images and ai_images are defined and not empty
        if not Human_images or not ai_images:  # Ensure ai_images is used
            raise ValueError("Image lists are empty or not defined.")

        images = random.sample(Human_images + ai_images, 10)  # Use ai_images
        return render_template("index.html", images=images)
    except Exception as e:
        print("Error in quiz route:", e)  # Print the error to the logs
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
    print("Image Stats Data Retrieved:", image_stats)

    return render_template("gallery.html", image_stats=image_stats)




@app.route("/submit", methods=["POST"])
def submit():
    data = request.json
    votes = data.get("votes", [])
    favorite = data.get("favorite")
    name = data.get("name")
    correct = 0

    if len(votes) != 10:
        return jsonify({"error": "You must make a selection for all 10 images."}), 400

    with get_db_connection() as conn:
        # Calculate score and update image stats
        for vote in votes:
            image = vote["image"]
            guessed_AI = vote["is_AI"]
            is_ai = "AI/" in image

            # Update correct score count
            if guessed_AI == is_AI:
                correct += 1

            # Update image stats in the database
            if guessed_AI:
                conn.execute('UPDATE image_stats SET AI_votes = AI_votes + 1 WHERE image = ?', (image,))
            else:
                conn.execute('UPDATE image_stats SET Human_votes = Human_votes + 1 WHERE image = ?', (image,))

        # Update favorite count
        conn.execute('UPDATE image_stats SET favorite_count = favorite_count + 1 WHERE image = ?', (favorite,))

        # Save player score
        conn.execute('INSERT INTO scores (name, score) VALUES (?, ?)', (name, correct))

    return jsonify({"score": correct})



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
