import time
from homework_bot import HomeworkBot
from vision_helper import VisionHelper

# ========= SET YOUR KEY HERE =========
API_KEY = "your_api_key"
# ====================================

bot = HomeworkBot()
vision = VisionHelper(api_key=API_KEY)

# ---- Tell the solver what filenames to look for ----
HEADER_TEMPLATES = {
    # use the three header crops you sent (rename them to match or add your own names)
    "fill": ["hdr_fill.png", "fill_header.png", "fill_in_blank_header.png"],
    "mc":   ["hdr_mc.png", "multiple_choice_header.png"],
    "ms":   ["hdr_ms.png", "multiple_select_header.png"],
    "tf":   ["hdr_tf.png", "true_false_header.png"],
}

CIRCLE_TEMPLATES = ["circle.png", "bubble.png"]      # radio buttons
SQUARE_TEMPLATES = ["square.png", "checkbox.png"]    # checkboxes
WORD_INPUT_TEMPLATES = ["word_input.png"]            # text field box

def pause(msg="⚠️ Paused. Press Enter to retry..."):
    input(msg)

def solve_one():
    # 0) Take a screenshot (used by GPT)
    shot = vision.capture_screen()

    # 1) Detect question type
    qtype = vision.find_question_type(HEADER_TEMPLATES)
    if not qtype:
        print("❌ Could not detect question type header.")
        pause()
        return

    print(f"Detected question type: {qtype}")

    if qtype == "fill":
        # Find all input boxes
        inputs = vision.find_word_inputs(WORD_INPUT_TEMPLATES)
        if not inputs:
            print("❌ No input boxes found.")
            pause()
            return

        # Ask GPT to provide answers for each blank (top->bottom, left->right)
        answers = vision.ask_fill_texts_from_image(shot, len(inputs))
        print("Answers:", answers)

        # Click each input and type the answer
        bot.type_into_inputs(inputs, answers)

    elif qtype == "mc":
        # Single choice — prefer circles, fall back to squares if needed
        opts = vision.find_circles(CIRCLE_TEMPLATES)
        if not opts:
            opts = vision.find_squares(SQUARE_TEMPLATES)
        if not opts:
            print("❌ No answer options found (circles/squares).")
            pause()
            return

        idx = vision.ask_mc_indices_from_image(shot, len(opts))
        if not idx:
            print("❌ GPT did not return a valid option index.")
            pause()
            return
        print("Clicking option:", idx)
        bot.click_indices(opts, idx)

    elif qtype == "ms":
        # Multi-select — prefer squares, fall back to circles if needed
        opts = vision.find_squares(SQUARE_TEMPLATES)
        if not opts:
            opts = vision.find_circles(CIRCLE_TEMPLATES)
        if not opts:
            print("❌ No answer options found (squares/circles).")
            pause()
            return

        idxs = vision.ask_ms_indices_from_image(shot, len(opts))
        if not idxs:
            print("❌ GPT did not return valid indices.")
            pause()
            return
        print("Clicking options:", idxs)
        bot.click_indices(opts, idxs)

    elif qtype == "tf":
    # True/False uses radio circles (top-to-bottom: usually True then False)
        opts = vision.find_circles(CIRCLE_TEMPLATES)
        if not opts:
            opts = vision.find_squares(SQUARE_TEMPLATES)  # fallback just in case
        if len(opts) < 2:
            print("❌ Expected two options for True/False.")
            pause()
            return

        # Ask GPT which of the two indices (1 or 2)
        idx = vision.ask_tf_index_from_image(shot)  # returns [1] or [2]
        if not idx:
            print("❌ GPT did not return 1 or 2 for TF.")
            pause()
            return

        print("Clicking TF option:", idx)
        bot.click_indices(opts, idx)


    else:
        print(f"❌ Unknown qtype: {qtype}")
        pause()
        return

        # 2) Confidence
    time.sleep(0.7)
    bot.press_high_confidence()
    time.sleep(0.7)

    # 3) If wrong, do: scroll -> reader -> questions
    if bot.recover_from_wrong():
        time.sleep(0.7)

    # 4) Next question
    if not bot.press_next_question():
        print("⚠️ Could not press Next Question")
    time.sleep(2)


if __name__ == "__main__":
    print("🟢 McGrawHill Solver running. Ctrl+C to stop.")
    try:
        while True:
            solve_one()
    except KeyboardInterrupt:
        print("\n🛑 Stopped.")
