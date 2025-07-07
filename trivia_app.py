import streamlit as st
import requests
import random
import html # To decode HTML entities from API response

# --- Configuration ---
OPENTDB_API_URL = "https://opentdb.com/api.php"
HISTORY_CATEGORY_ID = 23 # Category ID for History in Open Trivia DB

# Map our difficulty levels to Open Trivia DB's difficulty strings
DIFFICULTY_MAP = {
    1: "easy",
    2: "medium",
    3: "hard"
}

# --- Session State Initialization ---
# Initialize session state variables if they don't exist
if 'current_difficulty' not in st.session_state:
    st.session_state.current_difficulty = 1  # Start with easy questions
if 'score' not in st.session_state:
    st.session_state.score = 0
if 'feedback_message' not in st.session_state:
    st.session_state.feedback_message = ""
if 'asked_questions_ids' not in st.session_state:
    st.session_state.asked_questions_ids = [] # To keep track of question IDs already asked
if 'current_question_data' not in st.session_state:
    st.session_state.current_question_data = None
if 'all_fetched_questions' not in st.session_state:
    st.session_state.all_fetched_questions = {} # Store fetched questions by difficulty
if 'game_started' not in st.session_state:
    st.session_state.game_started = False

# --- Helper Functions ---
def fetch_questions_for_difficulty(difficulty_level):
    """Fetches a batch of questions for a given difficulty from Open Trivia DB."""
    difficulty_str = DIFFICULTY_MAP.get(difficulty_level)
    if not difficulty_str:
        return []

    params = {
        "amount": 10,  # Fetch 10 questions at a time
        "category": HISTORY_CATEGORY_ID,
        "difficulty": difficulty_str,
        "type": "multiple" # Open Trivia DB doesn't have a 'text' type, we'll extract answer from multiple choice
    }
    try:
        response = requests.get(OPENTDB_API_URL, params=params)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        if data["response_code"] == 0: # 0 means success
            processed_questions = []
            for q in data["results"]:
                # Decode HTML entities for question and answer
                question_text = html.unescape(q["question"])
                correct_answer = html.unescape(q["correct_answer"])
                processed_questions.append({
                    "question": question_text,
                    "answer": correct_answer,
                    "difficulty": difficulty_level,
                    "id": f"{q['category']}-{q['difficulty']}-{question_text}" # Simple unique ID
                })
            return processed_questions
        else:
            st.error(f"Error fetching questions from API (Code: {data['response_code']}). Please try again.")
            return []
    except requests.exceptions.RequestException as e:
        st.error(f"Network error fetching questions: {e}. Please check your internet connection.")
        return []

def get_next_question():
    """
    Selects the next question based on current difficulty.
    Fetches new questions if the current pool is exhausted.
    """
    current_diff = st.session_state.current_difficulty

    # Ensure we have questions for the current difficulty
    if current_diff not in st.session_state.all_fetched_questions or \
       not st.session_state.all_fetched_questions[current_diff]:
        with st.spinner(f"Fetching new {DIFFICULTY_MAP.get(current_diff, 'unknown')} history questions..."):
            new_questions = fetch_questions_for_difficulty(current_diff)
            if new_questions:
                # Filter out questions already asked in this game session
                fresh_questions = [q for q in new_questions if q["id"] not in st.session_state.asked_questions_ids]
                if fresh_questions:
                    st.session_state.all_fetched_questions[current_diff] = fresh_questions
                else:
                    # If newly fetched questions are all already asked, try fetching more or move on
                    st.session_state.feedback_message = "No new questions found at this difficulty. Trying to find more or moving on."
                    # This could lead to an infinite loop if only asked questions are returned.
                    # For simplicity, we'll just try to get one from the existing pool if available.
                    # A more robust solution might involve a session token with Open Trivia DB.
                    pass
            else:
                st.session_state.feedback_message = "Could not fetch questions. Please try restarting the game."
                st.session_state.current_question_data = None
                return

    # Filter questions by current difficulty that haven't been asked yet
    available_questions = [
        q for q in st.session_state.all_fetched_questions.get(current_diff, [])
        if q["id"] not in st.session_state.asked_questions_ids
    ]

    if not available_questions:
        # If all questions at current difficulty are exhausted (and no new ones could be fetched),
        # try to fetch questions for the next difficulty, or reset if all are exhausted.
        if current_diff < 3:
            st.session_state.feedback_message = "All questions at current difficulty exhausted. Moving to next difficulty."
            st.session_state.current_difficulty = min(current_diff + 1, 3)
            get_next_question() # Recursive call to get question at new difficulty
            return
        else:
            # All questions asked across all difficulties
            st.session_state.feedback_message = "You've answered all available questions! Click Restart to play again."
            st.session_state.current_question_data = None
            st.session_state.game_started = False # Indicate game is over
            return
    else:
        st.session_state.current_question_data = random.choice(available_questions)
        st.session_state.asked_questions_ids.append(st.session_state.current_question_data["id"])
        # Remove the question from the current pool to avoid re-asking in the same session
        st.session_state.all_fetched_questions[current_diff].remove(st.session_state.current_question_data)

def reset_game():
    """Resets all session state variables to restart the game."""
    st.session_state.current_difficulty = 1
    st.session_state.score = 0
    st.session_state.feedback_message = ""
    st.session_state.asked_questions_ids = []
    st.session_state.current_question_data = None
    st.session_state.all_fetched_questions = {}
    st.session_state.game_started = True # Mark game as started to fetch first question
    get_next_question() # Get the first question for the new game

# --- Streamlit UI ---
st.title("🌍 Dynamic History Trivia Challenge!")
st.markdown("Test your historical knowledge! Type your answer in the box below.")

# Start Game button for initial load
if not st.session_state.game_started:
    st.info("Click 'Start Game' to begin your history trivia challenge!")
    if st.button("Start Game"):
        reset_game()
        st.rerun()
    st.stop() # Stop execution until game starts

st.markdown(f"**Score:** {st.session_state.score} | **Difficulty:** {st.session_state.current_difficulty}")

# Display feedback message
if st.session_state.feedback_message:
    if "Correct!" in st.session_state.feedback_message:
        st.success(st.session_state.feedback_message)
    elif "Incorrect." in st.session_state.feedback_message:
        st.error(st.session_state.feedback_message)
    else:
        st.info(st.session_state.feedback_message)
    st.session_state.feedback_message = "" # Clear message after display

if st.session_state.current_question_data:
    question_data = st.session_state.current_question_data
    st.header(f"Question (Difficulty {question_data['difficulty']}):")
    st.write(question_data["question"])

    # Text input for user's answer
    user_answer = st.text_input("Your Answer:", key="user_answer_input").strip() # Strip whitespace

    if st.button("Submit Answer"):
        # Normalize answers for comparison (lowercase, remove extra spaces)
        normalized_user_answer = user_answer.lower()
        normalized_correct_answer = question_data["answer"].lower()

        # Simple check: direct match or contains the correct answer as a significant part
        # This can be improved with more sophisticated fuzzy matching if needed
        if normalized_user_answer == normalized_correct_answer or \
           (len(normalized_user_answer) > len(normalized_correct_answer) * 0.5 and normalized_correct_answer in normalized_user_answer):
            st.session_state.score += 1
            st.session_state.feedback_message = "Correct! 🎉"
            # Increase difficulty, but not beyond max difficulty (3)
            st.session_state.current_difficulty = min(st.session_state.current_difficulty + 1, 3)
        else:
            st.session_state.feedback_message = f"Incorrect. The correct answer was: **{question_data['answer']}** 😔"
            # Difficulty remains the same after an incorrect answer

        # Get the next question immediately after submission
        get_next_question()
        st.rerun() # Rerun to update the UI with new question and feedback
else:
    # This block will be shown if all questions are exhausted or an error occurred
    st.subheader("Game Over!")
    st.write(f"You've completed the trivia challenge! Your final score is: {st.session_state.score}")
    if st.button("Play Again"):
        reset_game()
        st.rerun()

# Always show the restart button at the bottom for convenience
st.markdown("---")
if st.button("Restart Game (Anytime)"):
    reset_game()
    st.rerun()

