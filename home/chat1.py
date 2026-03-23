import speech_recognition as sr
from googletrans import Translator
from gtts import gTTS
from playsound import playsound
import pickle
import pandas as pd
import os
import re
from word2number import w2n
import time
from django.conf import settings

# Load model
pickle_path = os.path.join(settings.MEDIA_ROOT, 'crop_model.pkl')
with open(pickle_path, 'rb') as f:
    model = pickle.load(f)

translator = Translator()

# Speak Telugu
def speak_in_telugu(text):
    try:
        tts = gTTS(text=text, lang='te')
        filename = "response.mp3"
        tts.save(filename)
        playsound(filename)
        os.remove(filename)
    except Exception as e:
        print("🔊 Error speaking:", e)

# Voice input
def get_voice_input(prompt_text):
    r = sr.Recognizer()
    with sr.Microphone() as source:
        speak_in_telugu(prompt_text)
        print(f"🗣️ {prompt_text}")
        audio = r.listen(source)

    try:
        text = r.recognize_google(audio, language='te-IN')
        print("👉 మీరు చెప్పారు:", text)
        return text
    except sr.UnknownValueError:
        print("❌ Could not understand audio")
        speak_in_telugu("గమనించలేకపోయాను, దయచేసి మళ్లీ ప్రయత్నించండి")
        return get_voice_input(prompt_text)
    except sr.RequestError as e:
        print("❌ Could not request results; {0}".format(e))
        speak_in_telugu("గూగుల్ సర్వర్ నుండి సమాధానం రాలేదు")
        return None

# Translate Telugu to English
def translate_to_english(text):
    try:
        translated = translator.translate(text, dest='en')
        print("🔤 Translation:", translated.text)
        return translated.text
    except Exception as e:
        print("❌ Translation Error:", e)
        return None

# Convert spoken number
def get_field_value(field_name, prompt_text):
    while True:
        telugu_input = get_voice_input(prompt_text)
        english_input = translate_to_english(telugu_input)
        if english_input:
            try:
                return float(english_input)
            except ValueError:
                try:
                    number = w2n.word_to_num(english_input.lower())
                    return float(number)
                except:
                    match = re.search(r"\d{2,}", english_input)
                    if match:
                        return float(match.group())
        speak_in_telugu("సరైన సంఖ్య చెప్పండి")

# Handle unknown queries
def handle_unknown_query():
    speak_in_telugu("క్షమించండి! నేను పరిమితమైన డేటాతో మాత్రమే శిక్షణ పొందాను.")
    speak_in_telugu("మీరు అడిగిన అన్ని ప్రశ్నలకు సమాధానం ఇవ్వాలంటే నాకు రియల్ టైం క్లౌడ్ శిక్షణ అవసరం.")
    print("⚡ Handled unknown query gracefully.")

# Prediction logic
def predict_crop():
    speak_in_telugu("పంట అంచనా కోసం డేటా సేకరిస్తున్నాను")

    N = get_field_value('N', "నైట్రోజన్ విలువ చెప్పండి")
    P = get_field_value('P', "ఫాస్ఫరస్ విలువ చెప్పండి")
    K = get_field_value('K', "పొటాషియం విలువ చెప్పండి")
    temp = get_field_value('temperature', "ఉష్ణోగ్రత చెప్పండి")
    humidity = get_field_value('humidity', "ఆర్ద్రత శాతం చెప్పండి")
    ph = get_field_value('ph', "పిహెచ్ విలువ చెప్పండి")
    rainfall = get_field_value('rainfall', "వర్షపాతం మిల్లీమీటర్లలో చెప్పండి")

    input_df = pd.DataFrame([[N, P, K, temp, humidity, ph, rainfall]],
                            columns=['N', 'P', 'K', 'temperature', 'humidity', 'ph', 'rainfall'])

    try:
        prediction = model.predict(input_df)[0]
        speak_in_telugu(f"మీకు సిఫారసు చేసిన పంట: {prediction}")
        print("✅ Suggested Crop:", prediction)

        return {
            'inputs': {
                'N': N, 'P': P, 'K': K,
                'Temperature': temp,
                'Humidity': humidity,
                'pH': ph,
                'Rainfall': rainfall
            },
            'prediction': prediction
        }

    except Exception as e:
        print("⚠️ Prediction Error:", e)
        speak_in_telugu("క్షమించండి! పంటను అంచనా వేయలేకపోయాను")
        return None

# Start chatbot loop
def start_chatbot():
    speak_in_telugu("హలో! ఇది వ్యవసాయ చాట్బాట్.")
    time.sleep(1)
    speak_in_telugu("మీరు ఎలా ఉన్నారు?")
    mood = get_voice_input("నాకు చెప్పండి")

    if mood:
        mood = mood.lower()

        # Respond if user asks "how are you"
        if any(word in mood for word in ["నువ్వు ఎలా ఉన్నావు", "how are you", "నువ్వు ఎలా ఉన్నావ్", "నువ్వు ఎలా ఉన్నారు"]):
            speak_in_telugu("హాహా నేను బాగున్నాను!")
        elif any(word in mood for word in ["బాగున్నాను", "సంతోషం", "happy", "fine", "good"]):
            speak_in_telugu("వినడానికి చాలా ఆనందంగా ఉంది!")
        elif any(word in mood for word in ["చెడు", "not", "sad", "బాగోలేదు"]):
            speak_in_telugu("అయితే మిమ్మల్ని సంతోషంగా మార్చటానికి నేను ఉన్నాను!")
        else:
            handle_unknown_query()

    # Ask to start prediction
    speak_in_telugu("పొలానికి అనువైన పంటను తెలుసుకోవాలంటే 'ప్రారంభించు' లేదా 'స్టార్ట్' అని చెప్పండి.")
    start_command = get_voice_input("ప్రారంభించాలా?")

    if start_command:
        start_command = start_command.lower()

        if any(keyword in start_command for keyword in ["ప్రారంభ", "start", "స్టార్ట్"]):
            result = predict_crop()
            return result
        else:
            handle_unknown_query()
            return None
    else:
        handle_unknown_query()
        return None

# Main
if __name__ == "__main__":
    start_chatbot()
