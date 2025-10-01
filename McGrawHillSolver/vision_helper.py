import pyautogui
from openai import OpenAI
import base64, re
from pathlib import Path
from typing import List, Tuple, Optional

RESOURCE_DIR = Path(__file__).parent  # where your PNGs live

def _exists(p: str | Path) -> bool:
    return (RESOURCE_DIR / p).exists()

def _full(p: str | Path) -> str:
    return str(RESOURCE_DIR / p)

class VisionHelper:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    # ---------- screen helpers ----------
    def capture_screen(self, path: str = "screenshot.png") -> str:
        out = RESOURCE_DIR / path
        img = pyautogui.screenshot()
        img.save(out)
        return str(out)

    def _encode_image_b64(self, path: str) -> str:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    # ---------- core locate + de-dup ----------
    def _locate_all_any(
        self,
        templates: List[str],
        confidences=(0.87, 0.83, 0.80, 0.76, 0.72),
        grayscale=True,
    ) -> List[Tuple[int, int]]:
        """
        Try multiple templates & confidences; return centers (x,y).
        Skips templates that don't exist.
        """
        hits: List[Tuple[int, int]] = []
        for conf in confidences:
            found_this_round = False
            for tpl in templates:
                if not _exists(tpl):
                    continue
                try:
                    matches = list(pyautogui.locateAllOnScreen(
                        _full(tpl), confidence=conf, grayscale=grayscale
                    ))
                    if matches:
                        hits.extend([pyautogui.center(m) for m in matches])
                        found_this_round = True
                except Exception:
                    continue
            if found_this_round:
                break
        # sort and de-duplicate
        hits.sort(key=lambda p: (p[1], p[0]))  # top->bottom, then left->right
        return self._dedupe_points(hits, min_dist=25)

    def _dedupe_points(self, pts: List[Tuple[int, int]], min_dist: int = 25) -> List[Tuple[int, int]]:
        """Merge near-duplicate coordinates (e.g., same input matched by multiple templates)."""
        deduped: List[Tuple[int, int]] = []
        for x, y in pts:
            keep = True
            for x2, y2 in deduped:
                if abs(x - x2) <= min_dist and abs(y - y2) <= min_dist:
                    keep = False
                    break
            if keep:
                deduped.append((x, y))
        return deduped

    # ---------- question-type detection ----------
    def find_question_type(self, header_map: dict) -> Optional[str]:
        for qtype, templates in header_map.items():
            pts = self._locate_all_any(templates)
            if pts:
                return qtype
        return None

    # ---------- element finders (now deduped) ----------
    def find_word_inputs(self, templates: List[str]) -> List[Tuple[int, int]]:
        return self._locate_all_any(templates)

    def find_circles(self, templates: List[str]) -> List[Tuple[int, int]]:
        return self._locate_all_any(templates)

    def find_squares(self, templates: List[str]) -> List[Tuple[int, int]]:
        return self._locate_all_any(templates)

    # ---------- GPT vision helpers ----------
    def _ask_gpt_with_image(self, image_path: str, text: str) -> str:
        b64 = self._encode_image_b64(image_path)
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": text},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                    ],
                }
            ],
        )
        return resp.choices[0].message.content.strip()

    def ask_mc_indices_from_image(self, screenshot_path: str, n: int) -> List[int]:
        prompt = (
            f"You see a Multiple Choice Question with {n} choices arranged top-to-bottom.\n"
            "Return ONLY the index (1-based) of the single best answer (just a number)."
        )
        out = self._ask_gpt_with_image(screenshot_path, prompt)
        m = re.search(r"\d+", out)
        if not m:
            return []
        k = int(m.group(0))
        return [k] if 1 <= k <= n else []

    def ask_ms_indices_from_image(self, screenshot_path: str, n: int) -> List[int]:
        prompt = (
            f"You see a Multiple Select Question with {n} choices top-to-bottom.\n"
            "Return ONLY all correct indices, comma-separated, no spaces, no text. Example: 1,3"
        )
        out = self._ask_gpt_with_image(screenshot_path, prompt)
        nums = [int(x) for x in re.findall(r"\d+", out)]
        return [k for k in nums if 1 <= k <= n]

    def ask_tf_index_from_image(self, screenshot_path: str) -> list[int]:
        """
        Decide True/False from the screenshot.
        Assume two top-to-bottom options: index 1 = True (top), index 2 = False (bottom).
        Return [1] or [2].
        """
        prompt = (
            "This is a True/False question. There are exactly two options top-to-bottom: "
            "index 1 = True (top), index 2 = False (bottom). "
            "Return ONLY the single index as a number: 1 or 2."
        )
        out = self._ask_gpt_with_image(screenshot_path, prompt).strip()
        m = re.search(r"\b([12])\b", out)
        return [int(m.group(1))] if m else []


    def ask_fill_texts_from_image(self, screenshot_path: str, n_fields: int) -> List[str]:
        """
        Return exactly n_fields answers. For single-blank cases,
        choose ONE best answer even if the model suggests several.
        """
        prompt = (
            "This is a Fill in the Blank question.\n"
            f"Provide exactly {n_fields} short answers for the blanks (top-to-bottom, left-to-right).\n"
            "Return each answer on its own line with NO extra text."
        )
        out = self._ask_gpt_with_image(screenshot_path, prompt).strip()

        # If there's only one blank, take the FIRST plausible token and ignore the rest.
        if n_fields == 1:
            # split by newline/commas/semicolons and take the first non-empty
            token = re.split(r"[\n,;]+", out)[0].strip()
            return [token] if token else [""]

        # Multi-blank: split into lines and trim/pad to n_fields
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        if len(lines) < n_fields:
            lines += [""] * (n_fields - len(lines))
        return lines[:n_fields]
