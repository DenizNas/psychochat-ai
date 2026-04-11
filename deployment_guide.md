# Psikochat-AI | Canlı Ortam (Production) Deployment Rehberi

Bu döküman, FastAPI, GPT ve SQLite altyapısına sahip Psikochat-AI uygulamasını Render, Azure veya kendi Ubuntu sanal sunucunuza (VPS) Docker ortamında nasıl "Production" seviyesinde deploy edeceğinizi gösterir.

## Ortak Gereksinimler & ENV Ayarları

Canlı ortama çıkmadan önce **gerçek (production)** bir `.env` dosyası hazırlamalısınız.

```env
ENVIRONMENT=production
OPENAI_API_KEY=YOUR_OPENAI_API_KEY_HERE
JWT_SECRET_KEY=Cok_guclu_rastgele_bir_sifre_uretin_ve_buraya_yazin
ADMIN_USER=admin_psiko
ADMIN_PASS=cok_guclu_admin_sifresi!123
```

> [!WARNING]
> `JWT_SECRET_KEY` değerini dev ortamındakinden (varsayılan) tamamen farklı yapmanız çok önemlidir. Aksi takdirde geliştirme ortamındaki JWT tokenları canlı ortamda geçerli sayılır.

---

## 🚀 Seçenek 1: Ubuntu VPS / Dedicated Server (DigitalOcean, Hetzner, AWS EC2, Azure VM)

Eğer tam yetkili bir sanal sunucunuz varsa, docker-compose yöntemi en hızlı ve kolay olanıdır.

**Adım 1:** Kodu sunucunuza klonlayın ve klasöre girin:
```bash
git clone <repo-url>
cd psikochat-ai
```

**Adım 2:** Prod için `.env` dosyanızı oluşturun:
```bash
nano .env
```
*(Yukarıdaki Ortak Gereksinimler bölümündeki içeriği yapıştırın ve kopyalayın).*

**Adım 3:** Uvicorn sunucusunu 4 Worker (işlemcik) ile ayağa kaldıran Prod dosyasını derleyin ve daemon (arkaplan) olarak çalıştırın:
```bash
docker-compose -f docker-compose.prod.yml up -d --build
```

**Adım 4 (Opsiyonel / Tavsiye Edilen):** Sistemi bir Reverse Proxy arkasına (Nginx) alarak `https://` (SSL) kurulumu yapın:
* Port 8000 dışarıya doğrudan açmak yerine, sunucunuza **Nginx** ve **Certbot(Let's Encrypt)** yükleyerek trafiği `proxy_pass http://127.0.0.1:8000;` şeklinde FastAPI containerına yönlendirin.

---

## 🚀 Seçenek 2: Render.com üzerinden otomatik Container Deployment

Render.com, "PaaS" (Platform as a Service) olarak Dockerfile entegrasyonu sunar ve yönetimsiz (serverless) konteyner barındırma hizmeti olarak çok idealdir.

1. **Dashboard'a Giriş:** Render'a girin ve **New > Web Service** seçin.
2. **Repository Bağlama:** GitHub reposunu Render'a bağlayın.
3. **Environment Seçimi:** Runtime olarak `Docker` seçeneğini ayarlayın.
4. **Volume Ekleme:** 
   - Sayfanın en altındaki "Advanced" ayarlarına girin.
   - **Disks** alanını bulun.
   - `Mount Path` olarak `/app/data` yazın ve boyut olarak en az 1GB (Loglama için) tahsis edin. Bu sayede uygulamanız Render tarafından uyutulsa/restart edilse dahi SQLite veritabanı silinmez.
5. **Environment Variables:** 
   - `.env` içerisindeki belirlediğiniz özellikleri (`OPENAI_API_KEY`, `JWT_SECRET_KEY` vs.) manuel olarak Render'ın Dashboard'undan ekleyin.
6. En alttan **Create Web Service** butonuna basın. Render otomatik build edecek ve https adresi verecektir.

---

## 🚀 Seçenek 3: Azure Web App for Containers

Eğer Azure Cloud Company yapısındaysanız Azure Web Apps ile kolayca Container deploy yapabilirsiniz.

1. **Docker İmajını Pushlamak:** Mevcut Dockerfile'ı kullanarak kodunuzu Azure Container Registry (ACR)'ye ya da public DockerHub'a pushlayın.
   ```bash
   docker build -t your-registry.azurecr.io/psikochat-ai:latest .
   docker push your-registry.azurecr.io/psikochat-ai:latest
   ```
2. **Web App Oluşturma:** Azure Portal'dan arama çubuğuna **App Services** yazıp yeni oluştur (`Create Web App`) deyin.
3. **Publish & OS:** Publish yöntemini **Docker Container**, Operation System (İşletim Sistemi)'ni ise **Linux** olarak seçin. 
4. **App Settings (Env):** "Configuration" (Yapılandırma) sekmesi altından `OPENAI_API_KEY`, `JWT_SECRET_KEY` gibi production değişkenlerini girin.
5. **Volume Mapping:** Azure Web App "Path Mappings" (Yol Eşleme) menüsünden **Azure Storage Account** kaynağınızı Mount Path olarak `/app/data` hedefine sabitleyin ki SQLite veritabanı yaşmaya devam etsin.
6. Deploy işlemi sonrası HTTPS otomatik tahsis edilecektir.

---
🎯 Tüm işlemlerden sonra `https://senin-domain.com/admin` rotasını test edip yetkisiz girişlerin Basic-Auth ve Bearer JWT sınırlarında kaldığını, mesaj kotalarının (SlowAPI Limit) çalıştığını görebilirsiniz!
