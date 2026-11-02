"""CSV numeric validity: a finite zero is observed; known nonfinite numbers are not."""
import math
def finite_number_text(text):
 return math.isfinite(float(text)) if text!='' else False
