# Manhwa Upscaler Bot v4

بوت Discord لتكبير صور المانهوا الملوّنة (Webtoon) — **GPU عند الطلب فقط** عبر RunPod Serverless.

## البنية

```
Discord (زر ⚡ Upscale → نافذة إدخال)
        │
        ▼
البوت (VPS صغير، 24/7 — بدون GPU)
  1. يحمّل الصور من الروابط (ZIP أو صور مباشرة)
  2. يرفعها إلى Cloudflare R2
  3. يرسل المهمة إلى RunPod Serverless
  4. يتابع التقدّم ويحدّث الرسالة
  5. يعرض رابط ZIP النهائي
        │
        ▼
RunPod Serverless GPU (يشتغل عند الطلب، يتوقف لصفر تلقائيًا)
  لكل صورة: Upscale (Real-ESRGAN anime) → تصغير لعرض 800px → JPEG
  عدد الصور وترتيبها لا يتغيّر أبدًا
```

**لماذا upscale ثم تصغير لـ800؟** لأن التكبير بالذكاء الاصطناعي ثم التصغير
(supersampling) يعطي خطوطًا وألوانًا أنظف بكثير من مجرد تغيير الحجم.

## الإعداد خطوة بخطوة

### 1) Discord

1. من [Discord Developer Portal](https://discord.com/developers/applications) أنشئ تطبيقًا جديدًا (أو **ولّد توكن جديد** — توكنات bot 3 القديمة مكشوفة في الكود ويجب إلغاؤها فورًا).
2. فعّل الـbot وانسخ التوكن إلى `DISCORD_TOKEN`.
3. ادعُ البوت لسيرفرك بصلاحيات: Send Messages, Embed Links, Use Application Commands.

### 2) Cloudflare R2

1. أنشئ حساب Cloudflare (مجاني) → قسم **R2**.
2. أنشئ bucket باسم `manhwa-upscale` (أو أي اسم — حدّثه في `.env`).
3. **Manage R2 API Tokens** → أنشئ token بصلاحية Object Read & Write.
4. انسخ: Account ID, Access Key ID, Secret Access Key.
5. (اختياري لكن موصى به) أضف **Lifecycle rule** على البادئة `jobs/` لحذف الملفات تلقائيًا بعد 7 أيام.

### 3) RunPod Serverless

1. أنشئ حساب على [runpod.io](https://runpod.io) واشحن رصيدًا.
2. ابنِ صورة الـworker وارفعها إلى Docker Hub:
   ```bash
   cd worker
   docker build -t YOUR_DOCKERHUB_USER/manhwa-upscaler:latest .
   docker push YOUR_DOCKERHUB_USER/manhwa-upscaler:latest
   ```
   > بديل: اربط RunPod بمستودع GitHub وسيبني الصورة تلقائيًا.
3. **Serverless → New Endpoint**:
   - Container Image: الصورة التي رفعتها
   - GPU: `RTX 4090` أو `RTX A4000` (كافٍ ورخيص)
   - **Min Workers: 0** ← هذا ما يجعل التكلفة صفرًا عند عدم الاستخدام
   - Max Workers: 1-2
   - Idle Timeout: 60 ثانية
   - Environment Variables: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`
4. انسخ **Endpoint ID** و**API Key** إلى `.env`.

### 4) تشغيل البوت (VPS)

```bash
cd bot
cp .env.example .env   # واملأ القيم
```

**بـ Docker (موصى به):**
```bash
cd ..
docker compose up -d --build
```

**أو مباشرة:**
```bash
pip install -r requirements.txt
python main.py
```

### 5) داخل Discord

1. اكتب `/panel` في القناة المطلوبة (يتطلب صلاحية Manage Messages) — تُنشر لوحة فيها زر **⚡ Upscale**.
2. أي شخص يضغط الزر → نافذة: الروابط + اسم العمل + الفصل + الجودة (اختياري).
3. البوت يتابع التقدّم في رسالة، وعند الانتهاء يظهر زر **⬇️ تحميل ZIP**.

## تغيير الموديل

الافتراضي `RealESRGAN_x4plus_anime_6B` (ممتاز للمانهوا الملوّنة).
لتغييره، أعد بناء صورة الـworker مع رابط موديل آخر (أي موديل يدعمه spandrel):

```bash
docker build --build-arg MODEL_URL="https://..." -t ...:latest .
```

خيارات: `realesr-animevideov3` (أسرع)، Real-CUGAN، أو أي `.pth` من openmodeldb.info.

## الإعدادات (bot/.env)

| المتغير | الافتراضي | الوصف |
|---|---|---|
| `OUT_WIDTH` | 800 | العرض النهائي (متطلب الموقع) |
| `JPEG_QUALITY` | 85 | جودة JPEG الافتراضية |
| `LINK_EXPIRE_HOURS` | 168 | صلاحية رابط التحميل (أقصاها 7 أيام) |
| `MAX_CONCURRENT_JOBS` | 2 | عدد المهام المتوازية |
| `JOB_TIMEOUT_MINUTES` | 30 | مهلة المهمة القصوى |

## التكلفة التقريبية

- **البوت:** VPS صغير ~5$/شهر (أو مجانًا على جهازك)
- **R2:** مجاني عمليًا (10GB تخزين مجاني + egress مجاني)
- **GPU:** بالثانية فقط أثناء المعالجة — فصل مانهوا (~50 صورة) يستغرق دقيقة أو دقيقتين على RTX 4090 (≈ سنتات قليلة)
