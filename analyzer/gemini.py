import json
import os
import re

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("models/gemini-2.5-flash")


def analyze_cv_with_gemini(cv_text: str) -> str:
    """
    Asks Gemini to analyze the CV and return a structured text response.
    The function now returns a single string, which is easier to parse.
    """
    prompt = f"""
        Aşağıdaki CV metnini analiz et. Cevabını aşağıdaki formatta, başlıkları tam olarak yazarak ver. 
        Her bir maddeyi tire (-) ile başlat.

        İyi Yönler:
        - [Madde 1]
        - [Madde 2]

        Eksikler:
        - [Madde 1]
        - [Madde 2]

        Genel Değerlendirme:
        [Tek paragraflık genel yorum]

        CV:
        \"\"\"
        {cv_text}
        \"\"\"
        """
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        # Return the error as a string for the view to handle
        return f"Gemini hatası: {str(e)}"


# --- SADECE BU FONKSİYONU GÜNCELLEYİN ---
def parse_analysis_text(analysis_text: str) -> dict:
    """
    Gemini'den gelen metni, küçük formatlama hatalarını ve boş maddeleri tolere ederek ayrıştırır.
    """
    parsed_data = {
        "good_points": [],
        "weaknesses": [],
        "general_assessment": ""
    }

    if analysis_text.startswith("Gemini hatası:"):
        parsed_data["error"] = analysis_text
        return parsed_data

    try:
        # İyi Yönler bölümünü bul ve ayıkla
        good_points_match = re.search(r'İyi Yönler:(.*?)(Eksikler:|Genel Değerlendirme:|$)', analysis_text,
                                      re.IGNORECASE | re.DOTALL)
        if good_points_match:
            content = good_points_match.group(1).strip()
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith(('-', '*')):
                    # Madde işaretini ve boşlukları temizle
                    item_text = line.lstrip('-* ').strip()
                    # *** YENİ KONTROL: Sadece içi dolu olan maddeleri listeye ekle ***
                    if item_text:
                        parsed_data["good_points"].append(item_text)

        # Eksikler bölümünü bul ve ayıkla
        weaknesses_match = re.search(r'Eksikler:(.*?)(Genel Değerlendirme:|$)', analysis_text,
                                     re.IGNORECASE | re.DOTALL)
        if weaknesses_match:
            content = weaknesses_match.group(1).strip()
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith(('-', '*')):
                    # Madde işaretini ve boşlukları temizle
                    item_text = line.lstrip('-* ').strip()
                    # *** YENİ KONTROL: Sadece içi dolu olan maddeleri listeye ekle ***
                    if item_text:
                        parsed_data["weaknesses"].append(item_text)

        # Genel Değerlendirme bölümünü bul ve ayıkla
        assessment_match = re.search(r'Genel Değerlendirme:(.*)', analysis_text, re.IGNORECASE | re.DOTALL)
        if assessment_match:
            content = assessment_match.group(1).strip()
            parsed_data["general_assessment"] = ' '.join(content.split())

    except Exception as e:
        print(f"Ayrıştırma hatası: {e}")
        parsed_data["error"] = "Analiz sonucu ayrıştırılırken bir hata oluştu."

    return parsed_data


def chatbot_answer_with_gemini(user_question: str, cv_text: str = "", analysis_text: str = "") -> str:
    prompt = f"""
Sen bir CV Chatbot Asistanısın. Aşağıda bir CV'nin metni ve bu CV hakkında yapılan bir analiz var.
Kullanıcıdan gelen soruya bu bağlamda, yani hem CV içeriğini hem de analiz sonuçlarını göz önünde bulundurarak cevap ver.


CV:
\"\"\"
{cv_text}
\"\"\"

Analiz:
\"\"\"
{analysis_text}
\"\"\"

Kullanıcının sorusu:
"{user_question}"

⚠️ Cevabın kısa, net ve faydalı olmalı. Gereksiz tekrar veya genel-geçer bilgi verme.
Spesifik örnekler ve önerilerle yardımcı ol.
"""
    try:
        safety_settings = {
            'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE',
            'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE',
            'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_NONE',
            'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_NONE',
        }

        print(f"DEBUG: chatbot_answer_with_gemini - Prompt oluşturuldu. İlk 100 karakter: {prompt[:100]}...")
        print(f"DEBUG: chatbot_answer_with_gemini - Gemini API çağrılıyor...")

        response = model.generate_content(prompt, safety_settings=safety_settings)

        print(f"DEBUG: chatbot_answer_with_gemini - Gemini API yanıtı alındı.")

        if not response.parts:
            try:
                block_reason = response.prompt_feedback.block_reason
                print(f"WARNING: chatbot_answer_with_gemini - Gemini yanıtı bloklandı. Neden: {block_reason}")
                return f"Üzgünüm, isteğiniz işlenemedi. Muhtemel sebep: Güvenlik filtresi ({block_reason}). Lütfen sorunuzu farklı bir şekilde sormayı deneyin."
            except Exception as e_block:
                print(f"ERROR: chatbot_answer_with_gemini - Bloklama nedeni alınırken hata: {str(e_block)}")
                return "Üzgünüm, bir sorun oluştu ve modelden bir cevap alınamadı. Lütfen tekrar deneyin."

        # Eğer buraya kadar geldiysek, yanıtın partları var demektir.
        # Şimdi response.text'e erişmeye çalışalım.
        # 'The string did not match the expected pattern' hatası genellikle
        # response.text'e erişmeye çalışıldığında, ancak yanıtın text() formatında olmaması durumunda oluşur.
        # Bu, Gemini'nin yanıtı farklı bir formatta (örneğin sadece tool_code) döndürmesi anlamına gelebilir.
        # Ancak Gemini-Flash genellikle doğrudan metin döndürür.
        # Olası bir durumda, yanıtın 'text' özelliğine güvenmeden önce kontrol etmek iyi olabilir.

        # Ek kontrol: response.text var mı?
        if hasattr(response, 'text') and response.text:
            print(f"DEBUG: chatbot_answer_with_gemini - Gemini cevabı: {response.text[:100]}...")
            return response.text.strip()
        else:
            print("ERROR: chatbot_answer_with_gemini - Gemini yanıtında metin içeriği bulunamadı.")
            # Yanıtın farklı bir formatta olup olmadığını kontrol edebiliriz (e.g. tool_code).
            # Eğer ihtiyacınız varsa, response.candidates[0].content.parts içinde ne olduğunu inceleyin.
            return "Üzgünüm, Gemini'dan beklentilerime uymayan bir yanıt aldım."

    except Exception as e:
        # Genel hata yakalama, bu en kritik kısım
        print(f"CRITICAL ERROR: Chatbot'ta beklenmedik bir hata oluştu: {e}")
        # Hata türünü daha spesifik yakalamak faydalı olabilir, örneğin:
        # from google.generativeai.types import HarmCategory, BlockedPromptException, StopCandidateException
        # if isinstance(e, BlockedPromptException):
        #     return f"İsteğiniz güvenlik nedeniyle engellendi: {e.block_reason}"
        return f"Sistemsel bir hata oluştu: {str(e)}"


def compare_cvs_with_gemini(old_cv_text: str, new_cv_text: str) -> str:
    prompt = f"""
Sen bir kariyer gelişim danışmanısın. Bir adayın ESKİ ve YENİ CV'lerini karşılaştırıyorsun.
Görevin, YENİ CV'de ESKİ CV'ye kıyasla yapılan olumlu değişiklikleri, eklemeleri ve gelişim alanlarını tespit etmektir.

Cevabını madde madde, kısa ve net bir şekilde aşağıdaki formatta hazırla:

**Önceki CV'ye Göre Gelişmeler:**
- [Tespit ettiğin ilk önemli ekleme/değişiklik. Örneğin: "Yeni projeler bölümüne 'E-Ticaret Platformu' eklendi."]
- [Tespit ettiğin ikinci önemli ekleme/değişiklik. Örneğin: "Yetenekler listesine 'Docker' ve 'Kubernetes' dahil edildi."]
- [Tespit ettiğin diğer değişiklikler...]

**Genel Gelişim Yorumu:**
[1-2 cümlelik, motive edici bir özet. Örneğin: "Yeni CV'niz, özellikle teknik yetenekler ve proje deneyimi alanlarında kaydettiğiniz somut ilerlemeyi harika bir şekilde yansıtıyor. Başarılar!"]

Eğer anlamlı bir değişiklik yoksa, sadece "Önceki CV'ye göre belirgin bir değişiklik tespit edilmedi." yaz.

---
ESKİ CV:
\"\"\"
{old_cv_text}
\"\"\"
---
YENİ CV:
\"\"\"
{new_cv_text}
\"\"\"
"""
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Karşılaştırma sırasında Gemini hatası: {str(e)}"


def extract_cv_data_with_gemini(cv_text: str) -> dict:
    """
    Verilen CV metnini Gemini kullanarak analiz eder ve yapılandırılmış bir
    sözlük (dictionary) olarak döndürür. Hata durumunda hata mesajı içeren bir sözlük döndürür.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        return {"error": "Gemini API anahtarı yapılandırılmamış."}

    # Gemini'ye vereceğimiz talimat (Prompt). Bu kısım çok önemli.
    prompt = f"""
    Aşağıdaki CV metnini analiz et ve bilgileri KESİNLİKLE aşağıdaki JSON formatında çıkar.
    Eğer bir bilgi yoksa, alanları boş string "" veya boş liste [] olarak bırak.
    JSON nesnesinin dışında KESİNLİKLE hiçbir açıklama veya ek metin ekleme. Sadece saf JSON döndür.

    JSON Formatı:
    {{
      "personalInfo": {{
        "fullName": "",
        "email": "",
        "phone": "",
        "address": ""
      }},
      "summary": "",
      "workExperience": [
        {{
          "jobTitle": "",
          "company": "",
          "location": "",
          "startDate": "",
          "endDate": "",
          "description": ""
        }}
      ],
      "education": [
        {{
          "degree": "",
          "institution": "",
          "location": "",
          "graduationDate": ""
        }}
      ],
      "skills": [],
      "languages": [
        {{
          "name": "Konuşulan dilin adı (örn: İngilizce)",
          "level": "Dilin seviyesi (örn: C1 - İleri Seviye)"
        }}
      ],
      
      "certificates": [
        {{
          "name": "Sertifikanın tam adı",
          "issuer": "Sertifikayı veren kurum"
        }}
      ],
    }}
          // Örn: ["Google Data Analytics Professional Certificate", "Certified ScrumMaster (CSM)"]

    CV Metni:
    ---
    {cv_text}
    ---
    """

    try:
        response = model.generate_content(prompt)

        # Gemini bazen cevabın başına ve sonuna ```json ... ``` ekleyebilir, bunları temizleyelim.
        cleaned_text = response.text.strip().replace("```json", "").replace("```", "").strip()

        # Gelen metnin geçerli bir JSON olup olmadığını kontrol et
        cv_data = json.loads(cleaned_text)
        return cv_data  # Başarılı olursa dict'i döndür

    except json.JSONDecodeError:
        print(f"HATA: Gemini geçerli bir JSON döndürmedi. Dönen metin:\n{response.text}")
        return {"error": "AI'dan gelen veri ayrıştırılamadı. Lütfen tekrar deneyin."}
    except Exception as e:
        print(f"HATA: Gemini API çağrısı sırasında bir hata oluştu: {e}")
        return {"error": f"AI servisine bağlanırken bir sorun oluştu: {str(e)}"}


def generate_summary_text(name: str = "", skills: str = "", education: str = "", experience: str = "") -> str:
    """
    Kullanıcının adı, yetenekleri, eğitimi ve deneyimine göre profesyonel bir özgeçmiş özeti üretir.
    """
    prompt = f"""
    
    Aşağıdaki bilgilerle profesyonel bir özgeçmiş özeti (CV Summary) yaz Yalnızca özet metni üret. Giriş, kapanış veya açıklama yazma.:

    - İsim: {name}
    - Yetenekler: {skills}
    - Eğitim: {education}
    - Deneyim: {experience}

    ➤ 3-4 satırlık kısa, etkili ve profesyonel bir özet oluştur.
    ➤ İngilizce yaz.
    ➤ Özet, özgün ve akıcı olsun; tekrar veya ezber cümlelerden kaçın.
    ➤ Kişisel yetkinlikleri ve güçlü yönleri vurgula.
    >
    """

    try:
        response = model.generate_content(prompt)
        # Gemini bazen yanıtı farklı bir formatta döndürebilir veya boş olabilir.
        # response.text'in varlığını ve içeriğini kontrol etmek önemlidir.
        if hasattr(response, 'text') and response.text:
            return response.text.strip()
        else:
            print(f"DEBUG: Gemini'dan boş veya metin içermeyen bir yanıt geldi. Feedback: {response.prompt_feedback}")
            return "Gemini'dan geçerli bir metin yanıtı alınamadı."  # Anlaşılır bir mesaj döndürün
    except Exception as e:
        print(f"DEBUG: Gemini API çağrısı sırasında hata: {e}")  # Sunucu konsoluna yazdır
        # API anahtarının geçersiz olması veya kota aşımı gibi durumlar burada yakalanır.
        return f"Gemini özgeçmiş özeti oluşturma hatası: {str(e)}"


def translate_cv_data_with_gemini(cv_data: dict, target_language: str) -> dict:
    """
    Verilen yapılandırılmış CV verilerini (dictionary) Gemini kullanarak hedef dile çevirir.
    Dönen çevrilmiş verilerin JSON formatında olması beklenir.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        return {"error": "Gemini API anahtarı yapılandırılmamış."}

    # Hedef dilin tam adını belirleyelim
    lang_map = {
        "en": "İngilizce",
        "tr": "Türkçe",
        "de": "Almanca"
        # Desteklemek istediğiniz diğer dilleri buraya ekleyin
    }
    lang_name = lang_map.get(target_language, "İngilizce") # Varsayılan olarak İngilizce

    # Çevrilecek CV verisini JSON string'ine dönüştür
    cv_json_string = json.dumps(cv_data, ensure_ascii=False, indent=2)

    prompt = f"""
    Aşağıdaki CV verilerini (JSON formatında) baştan sona "{lang_name}" diline çevir.
    Tüm metinsel alanları (personalInfo içindeki fullName, summary, workExperience içindeki jobTitle, company, description; education içindeki degree, institution; certificates içindeki name, issuer; skills listesi elemanları, languages içindeki name ve level alanları, hobbies listesi elemanları) çevir.
    Çevrilen verileri aynı JSON yapısında geri döndür.
    JSON nesnesinin dışında KESİNLİKLE hiçbir açıklama veya ek metin ekleme. Sadece saf JSON döndür.

    Çevrilecek CV Verisi:
    ---
    {cv_json_string}
    ---
    """

    try:
        response = model.generate_content(prompt)
        cleaned_text = response.text.strip().replace("```json", "").replace("```", "").strip()

        # JSON başlangıcı ve sonunu bulma, `extract_cv_data_with_gemini`'deki gibi daha sağlam bir yaklaşım
        json_start = cleaned_text.find('{')
        json_end = cleaned_text.rfind('}')

        if json_start != -1 and json_end != -1 and json_end > json_start:
            cleaned_text = cleaned_text[json_start : json_end + 1]
        else:
            print(f"UYARI: translate_cv_data_with_gemini - JSON başlangıç/bitiş karakterleri bulunamadı veya hatalı. Ham metin:\n{cleaned_text}")
            # Bu durumda, sadece temizlenmiş ham metni denemek zorunda kalabiliriz,
            # ancak bu JSONDecodeError'a yol açabilir.
            # Hata ayıklama için bu noktayı dikkatle inceleyin.


        translated_cv_data = json.loads(cleaned_text)
        return translated_cv_data

    except json.JSONDecodeError as e:
        print(f"HATA: translate_cv_data_with_gemini geçerli bir JSON döndürmedi. Hata: {e}. Dönen metin:\n{cleaned_text}")
        return {"error": f"AI'dan gelen çevrilmiş veri ayrıştırılamadı. Hata: {e}"}
    except Exception as e:
        print(f"HATA: translate_cv_data_with_gemini API çağrısı sırasında bir hata oluştu: {e}")
        return {"error": f"AI servisine bağlanırken bir sorun oluştu: {str(e)}"}