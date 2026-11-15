import cv2
import os
import sys

sys.path.append(r"d:\Projects\MTCasinoScript")
from bot.vision_engine import VisionEngine

ve = VisionEngine(templates_dir=r"d:\Projects\MTCasinoScript\bot\templates")

# Test 1: PayDay detection
payday_img = cv2.imread(r"C:\Users\user\.gemini\antigravity\brain\32c77e7d-50c9-423e-9f18-f34ef4c773ae\.user_uploaded\media_1794699057841_97a04d37.jpg")
is_payday, close_pt = ve.is_payday_popup_present(payday_img)
print(f"Test 1 - PayDay present: {is_payday}, close button: {close_pt}")
assert is_payday, "Payday should be detected!"

# Test 2: Casino dialog detection
f1 = cv2.imread(r"C:\Users\user\.gemini\antigravity\brain\32c77e7d-50c9-423e-9f18-f34ef4c773ae\video_frames\time_01s.jpg")
bounds = ve.detect_casino_dialog(f1)
print(f"Test 2 - Dialog bounds: {bounds}")
assert bounds is not None, "Casino dialog should be detected!"

pts = ve.get_ui_click_points(bounds)
print(f"Test 2 - UI click points: {pts}")

# Test 3: Outcome detection on f7 (number 4 -> BLACK)
f7 = cv2.imread(r"C:\Users\user\.gemini\antigravity\brain\32c77e7d-50c9-423e-9f18-f34ef4c773ae\video_frames\time_07s.jpg")
bounds7 = ve.detect_casino_dialog(f7)
num7, out7, score7 = ve.detect_winning_number(f7, bounds7)
print(f"Test 3 - f7 detected number: {num7}, outcome: {out7}, score: {score7}")
assert num7 == 4 and out7 == 'BLACK', f"Expected (4, BLACK), got ({num7}, {out7})"

# Test 4: Outcome detection on f4 (number 18 -> BLACK)
f4 = cv2.imread(r"C:\Users\user\.gemini\antigravity\brain\32c77e7d-50c9-423e-9f18-f34ef4c773ae\video_frames\frame_04.jpg")
bounds4 = ve.detect_casino_dialog(f4)
num4, out4, score4 = ve.detect_winning_number(f4, bounds4)
print(f"Test 4 - f4 detected number: {num4}, outcome: {out4}, score: {score4}")
assert num4 == 18 and out4 == 'BLACK', f"Expected (18, BLACK), got ({num4}, {out4})"

# Test 5: Outcome detection on f38 (number 30 -> RED)
f38 = cv2.imread(r"C:\Users\user\.gemini\antigravity\brain\32c77e7d-50c9-423e-9f18-f34ef4c773ae\video_frames\time_38s.jpg")
bounds38 = ve.detect_casino_dialog(f38)
num38, out38, score38 = ve.detect_winning_number(f38, bounds38)
print(f"Test 5 - f38 detected number: {num38}, outcome: {out38}, score: {score38}")
assert num38 == 30 and out38 == 'RED', f"Expected (30, RED), got ({num38}, {out38})"

# Test 6: Button ready check
ready1 = ve.is_play_button_ready(f1, bounds)
print(f"Test 6 - f1 play button ready: {ready1}")

print("\nALL VISION ENGINE TESTS PASSED PERFECTLY!")
