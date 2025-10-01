import pyautogui, time
from typing import List, Tuple

class HomeworkBot:
    def __init__(self, pause_time: float = 0.8):
        pyautogui.PAUSE = pause_time

    # ---------- basic clicks/typing ----------
    def click(self, x: int, y: int):
        pyautogui.click(x, y)

    def click_points(self, points: List[Tuple[int, int]], delay: float = 0.4):
        for (x, y) in points:
            pyautogui.click(x, y)
            time.sleep(delay)

    def click_indices(self, points: List[Tuple[int, int]], indices_1based: List[int], delay: float = 0.4):
        for idx in indices_1based:
            if 1 <= idx <= len(points):
                x, y = points[idx - 1]
                pyautogui.click(x, y)
                time.sleep(delay)

    def type_into_inputs(self, inputs: List[Tuple[int, int]], texts: List[str], delay: float = 0.3):
        for (x, y), txt in zip(inputs, texts):
            pyautogui.click(x, y)          # focus
            time.sleep(0.15)
            pyautogui.hotkey("ctrl", "a")
            pyautogui.press("backspace")
            if txt:
                pyautogui.typewrite(txt, interval=0.03)
            time.sleep(delay)

    # ---------- image helpers ----------
    def _locate_center(self, filename: str, confidences=(0.87, 0.83, 0.80, 0.76), grayscale=True):
        for conf in confidences:
            try:
                loc = pyautogui.locateCenterOnScreen(filename, confidence=conf, grayscale=grayscale)
            except Exception:
                loc = None
            if loc:
                return loc
        return None

    def _click_image(self, filename: str, confidences=(0.87, 0.83, 0.80, 0.76), grayscale=True) -> bool:
        loc = self._locate_center(filename, confidences=confidences, grayscale=grayscale)
        if loc:
            pyautogui.click(loc)
            return True
        return False

    # ---------- navigation buttons ----------
    def press_high_confidence(self) -> bool:
        if self._click_image("high.png"):
            return True
        print("High button not found")
        return False

    def press_next_question(self) -> bool:
        if self._click_image("next_question.png"):
            return True
        print("Next Question button not found")
        return False

    # ---------- NEW: wrong-answer recovery ----------
    def _is_wrong_shown(self) -> bool:
        """Detect the red X (wrong.png)."""
        return self._locate_center("wrong.png") is not None

    def _quick_scroll_down(self, distance: int = -1200):
        """Negative scroll goes down on Windows/macOS."""
        try:
            pyautogui.scroll(distance)
        except Exception:
            # Fallback: PageDown once
            pyautogui.press("pagedown")

    def recover_from_wrong(self) -> bool:
        """
        If wrong.png is visible:
          1) Scroll down once
          2) Click reader.png (Clarify with AI Reader)
          3) Click questions.png (To Questions)
        Returns True if handled, False otherwise.
        """
        if not self._is_wrong_shown():
            return False

        print("❌ Wrong detected — performing recovery flow...")
        # 1) scroll once (fast, fixed distance)
        self._quick_scroll_down(-1200)
        time.sleep(0.4)

        # 2) open reader (Clarify/Read)
        if not self._click_image("reader.png"):
            print("Reader button not found after scroll.")
            return False
        time.sleep(3)  # let the article/page load

        # 3) back to questions
        if not self._click_image("questions.png"):
            print("To Questions button not found.")
            return False

        print("✅ Recovery done (Reader -> To Questions).")
        return True

    # Legacy (kept for completeness)
    def handle_wrong_answer(self) -> bool:
        ok1 = self._click_image("reader.png")
        if ok1:
            time.sleep(3)
        ok2 = self._click_image("questions.png")
        if ok2:
            return True
        print("Could not complete Read->Back flow")
        return False
