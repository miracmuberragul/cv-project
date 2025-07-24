from django.http import JsonResponse
from django.shortcuts import render, redirect
from .models import Resume
import json
from .gemini import analyze_cv_with_gemini, chatbot_answer_with_gemini, parse_analysis_text, extract_cv_data_with_gemini, generate_summary_text
import difflib

# views.py (eklemeler)
from django.views.decorators.csrf import csrf_exempt



def create_cv_page(request):
    """Sadece boş CV oluşturma sayfasını render eder."""
    return render(request, 'analyzer/create.html')


@csrf_exempt
def parse_pdf_for_edit(request):
    if request.method == "POST":
        # ... (PDF okuma kodunuz aynı kalır) ...
        reader = PdfReader(request.FILES.get('pdf_file'))
        full_text = "".join(page.extract_text() or "" for page in reader.pages)

        if not full_text.strip():
            return JsonResponse({"error": "PDF'ten metin okunamadı."}, status=400)

        # Gemini'den yapılandırılmış dict verisini al
        cv_data = extract_cv_data_with_gemini(full_text)

        # Fonksiyonun bir hata döndürüp döndürmediğini kontrol et
        if "error" in cv_data:
            # Eğer hata varsa, hatayı frontend'e bildir ve 500 koduyla cevap ver
            return JsonResponse(cv_data, status=500)

        # Hata yoksa, başarılı veriyi frontend'e gönder
        return JsonResponse(cv_data)

    return JsonResponse({"error": "Sadece POST metodu desteklenir."}, status=405)


def download_cv_as_pdf(request):
    """
    Bu fonksiyon şimdilik bir placeholder.
    İleride WeasyPrint gibi bir kütüphane ile HTML'den PDF üretecek.
    """
    # Bu kısmı daha sonra dolduracağız.
    from django.http import HttpResponse
    return HttpResponse("PDF İndirme özelliği yakında!", content_type="text/plain")
def home(request):
    return render(request, 'analyzer/homepage.html')

def analyze_pdf_text(text):
    result = []
    if "hobiler" not in text.lower():
        result.append("Hobiler kısmı eksik.")
    if "başarı" not in text.lower():
        result.append("Başarılar listelenmemiş.")
    if "iletişim" not in text.lower():
        result.append("İletişim bilgileri eksik olabilir.")
    return result or ["CV yeterince detaylı görünüyor."]

from PyPDF2 import PdfReader



def upload_and_analyze(request):
    if request.method == "POST":
        pdf_file = request.FILES.get('pdf_file')
        if not pdf_file:
            return JsonResponse({"error": "Dosya seçilmedi."}, status=400)

        reader = PdfReader(pdf_file)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() or ""

        if not full_text.strip():
            return JsonResponse({"error": "PDF dosyasından metin okunamadı veya dosya boş."}, status=400)

        try:
            # 1. Get the raw analysis text from Gemini
            analysis_text = analyze_cv_with_gemini(full_text)

            # 2. Parse the text into a structured dictionary
            analysis_data = parse_analysis_text(analysis_text)

            # Check if parsing resulted in an error
            if "error" in analysis_data:
                return JsonResponse({"error": analysis_data["error"]}, status=500)

            # Save to database (optional, but good practice)
            # You might want to save the structured JSON instead of the raw text
            Resume.objects.create(
                pdf_file=pdf_file,
                analysis_result=json.dumps(analysis_data, ensure_ascii=False)  # Store as JSON string
            )

            # 3. Save necessary info to the session for the chatbot
            request.session['cv_text'] = full_text
            request.session['analysis_text'] = analysis_text  # Save the original raw text for context

            # 4. Return the structured JSON that the frontend expects
            return JsonResponse(analysis_data)

        except Exception as e:
            # Catch any other unexpected server errors
            print(f"Sunucu hatası: {str(e)}")  # Log the error for debugging
            return JsonResponse({"error": f"Sunucuda beklenmedik bir hata oluştu: {str(e)}"}, status=500)

    resumes = Resume.objects.all().order_by('-uploaded_at')
    return render(request, 'analyzer/upload.html', {
        "resumes": resumes,
    })


def chatbot(request):
    # 'from .gemini import chatbot_answer_with_gemini' üstte zaten var, tekrar etmeye gerek yok
    # 'import json' üstte zaten var, tekrar etmeye gerek yok

    if request.method == "POST":
        cv_text = request.session.get("cv_text", "") # Varsayılan değer ekledik
        analysis_text = request.session.get("analysis_text", "") # Varsayılan değer ekledik

        if not cv_text.strip(): # Metin tamamen boşluklardan oluşuyorsa da kabul etmez
            return JsonResponse({
                "answer": "Lütfen önce bir CV yükleyip analiz edin. Sohbet edebilmem için bir CV'ye ihtiyacım var."
            }, status=400) # 400 Bad Request, çünkü istemci bir ön koşulu sağlamadı

        try:
            data = json.loads(request.body)
            question = data.get("question", "").strip() # .strip() ile boşlukları temizle

            if not question:
                return JsonResponse({"error": "Soru boş olamaz."}, status=400)

            # Gemini fonksiyonunu çağırıyoruz
            answer = chatbot_answer_with_gemini(question, cv_text, analysis_text)
            return JsonResponse({"answer": answer})

        except json.JSONDecodeError:
            return JsonResponse({"error": "Geçersiz JSON formatı."}, status=400)
        except Exception as e:
            # Detaylı hata mesajı loglama
            print(f"Chatbot servisinde beklenmedik hata: {e}")
            return JsonResponse({"error": f"Sistemde bir sorun oluştu: {str(e)}"}, status=500)

    # Sadece POST metodunu desteklediğimizi belirtmek için
    return JsonResponse({"error": "Sadece POST metodu desteklenir."}, status=405)

def compare_cv_versions(old_cv: str, new_cv: str) -> list[str]:
    # Boş veri varsa direkt çık
    if not old_cv or not new_cv:
        return ["Yeterli veri yok."]

    # Benzeme oranı (%100'e yakınsa değişiklik yok sayılır)
    similarity = difflib.SequenceMatcher(None, old_cv, new_cv).ratio()
    if similarity > 0.97:
        return []

    # Detaylı fark çıkar (kelime bazlı)
    diff = difflib.ndiff(old_cv.split(), new_cv.split())
    additions = [line[2:] for line in diff if line.startswith("+ ")]

    # Anlamsız boşluk/artık veri temizliği
    meaningful_additions = [
        item for item in additions if len(item.strip()) > 2 and not item.isnumeric()
    ]

    return meaningful_additions


@csrf_exempt
def generate_summary(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            name = data.get('name', '').strip()
            skills = data.get('skills', '').strip()
            education = data.get('education', '').strip()
            experience = data.get('experience', '').strip()

            if not any([name, skills, education, experience]):
                return JsonResponse({'error': 'Lütfen tüm alanları doldurun.'}, status=400)

            # Gemini ile AI özeti oluştur
            prompt = f"""
            Aşağıdaki bilgileri kullanarak profesyonel bir kariyer özeti (3-4 cümlelik) oluştur:
            İsim: {name}
            Yetenekler: {skills}
            Eğitim: {education}
            Deneyim: {experience}
            """
            summary = generate_summary_text(prompt)

            return JsonResponse({'summary': summary})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Sadece POST isteklerine izin verilir.'}, status=405)