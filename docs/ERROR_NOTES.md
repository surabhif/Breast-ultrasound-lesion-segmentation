# Error notes (mistakes explorer)

**Source:** AI-generated analysis (Cursor agent), not clinician-authored. Research demo only.

- `normal/normal (126).png` (false_lesion_on_normal, Dice 0.00): Model drew a lesion-like region on a normal study — classic over-call; calipers/texture may cue a false blob.
- `normal/normal (28).png` (false_lesion_on_normal, Dice 0.00): Model drew a lesion-like region on a normal study — classic over-call; calipers/texture may cue a false blob.
- `normal/normal (94).png` (false_lesion_on_normal, Dice 0.00): Model drew a lesion-like region on a normal study — classic over-call; calipers/texture may cue a false blob.
- `normal/normal (92).png` (false_lesion_on_normal, Dice 0.00): Model drew a lesion-like region on a normal study — classic over-call; calipers/texture may cue a false blob.
- `benign/benign (114).png` (missed_lesion, Dice 0.00): Near-zero Dice: lesion was essentially missed. Low contrast or small lesion size is a common cause in BUSI.
- `normal/normal (116).png` (false_lesion_on_normal, Dice 0.00): Model drew a lesion-like region on a normal study — classic over-call; calipers/texture may cue a false blob.
- `normal/normal (81).png` (false_lesion_on_normal, Dice 0.00): Model drew a lesion-like region on a normal study — classic over-call; calipers/texture may cue a false blob.
- `normal/normal (23).png` (false_lesion_on_normal, Dice 0.00): Model drew a lesion-like region on a normal study — classic over-call; calipers/texture may cue a false blob.
- `benign/benign (61).png` (missed_lesion, Dice 0.00): Near-zero Dice: lesion was essentially missed. Low contrast or small lesion size is a common cause in BUSI.
- `normal/normal (80).png` (false_lesion_on_normal, Dice 0.00): Model drew a lesion-like region on a normal study — classic over-call; calipers/texture may cue a false blob.
- `benign/benign (122).png` (missed_lesion, Dice 0.00): Near-zero Dice: lesion was essentially missed. Low contrast or small lesion size is a common cause in BUSI.
- `benign/benign (108).png` (missed_lesion, Dice 0.00): Near-zero Dice: lesion was essentially missed. Low contrast or small lesion size is a common cause in BUSI.
- `normal/normal (77).png` (false_lesion_on_normal, Dice 0.00): Model drew a lesion-like region on a normal study — classic over-call; calipers/texture may cue a false blob.
- `benign/benign (94).png` (missed_lesion, Dice 0.00): Near-zero Dice: lesion was essentially missed. Low contrast or small lesion size is a common cause in BUSI.
- `normal/normal (60).png` (false_lesion_on_normal, Dice 0.00): Model drew a lesion-like region on a normal study — classic over-call; calipers/texture may cue a false blob.
- `normal/normal (69).png` (false_lesion_on_normal, Dice 0.00): Model drew a lesion-like region on a normal study — classic over-call; calipers/texture may cue a false blob.
- `normal/normal (58).png` (false_lesion_on_normal, Dice 0.00): Model drew a lesion-like region on a normal study — classic over-call; calipers/texture may cue a false blob.
- `benign/benign (116).png` (missed_lesion, Dice 0.00): Near-zero Dice: lesion was essentially missed. Low contrast or small lesion size is a common cause in BUSI.
- `benign/benign (119).png` (missed_lesion, Dice 0.00): Near-zero Dice: lesion was essentially missed. Low contrast or small lesion size is a common cause in BUSI.
- `benign/benign (242).png` (missed_lesion, Dice 0.06): Near-zero Dice: lesion was essentially missed. Low contrast or small lesion size is a common cause in BUSI.
- `malignant/malignant (177).png` (boundary_disagreement, Dice 0.16): Moderate Dice: overall location is plausible but the contour disagrees (margin / caliper influence).
- `benign/benign (37).png` (wrong_class, Dice 0.21): Benign/malignant score disagreed with the label at the 0.5 operating point — auxiliary head error, not only segmentation.
- `benign/benign (394).png` (boundary_disagreement, Dice 0.27): Moderate Dice: overall location is plausible but the contour disagrees (margin / caliper influence).
- `benign/benign (383).png` (boundary_disagreement, Dice 0.34): Moderate Dice: overall location is plausible but the contour disagrees (margin / caliper influence).
