# New Build Tender Dashboard

لوحة مناقصات New Build LLC — نسخة GitHub Pages.

## النشر
1. ارفع **محتويات** هذا المجلد إلى جذر مستودع GitHub العام (`main`)، بما فيها `.github/workflows/update.yml`.
2. Settings → Pages → Deploy from a branch → `main` → `/ (root)` → Save.
3. Actions → Update New Build tenders → Run workflow للاختبار.
4. افتح رابط GitHub Pages من Settings → Pages.

## التحديث
التشغيل مجدول الساعة 12:00 و16:00 بتوقيت دمشق (09:00 و13:00 UTC) وقد يتأخر تنفيذ GitHub. يعيد تحديث `tenders.json` باستبعاد المنتهي والتكرار، ويقرأ `manual_tenders.csv` وأي مصادر JSON متوافقة مفعلّة في `sources.json`.

**تنبيه:** لم يتم توصيل السحب التلقائي من تلغرام أو فيسبوك أو مواقع المناقصات بعد؛ كما أن `tenders.json` يبدأ فارغاً، ولا يجوز اعتبار عدم عرض مناقصات دليلاً على عدم وجودها. إدخال مصدر في `sources.json` يتطلب رابط HTTPS يرجع قائمة JSON سجلات مؤكدة بحقول issuer,title,deadline (YYYY-MM-DD),url. لا تضع مفاتيح سرية في المستودع العام.

الملف `index.html` هو آخر واجهة موسعة محفوظة بتاريخ 20 تشرين الأول 2026، وتضم دليل الجهات. أي سجلات معروضة مدمجة داخل الواجهة هي بيانات سابقة وليست رصداً مباشراً متجدداً.
