#!/bin/bash
# Yeni GitHub Repo Oluşturma Scripti

echo "🚀 Yeni GitHub Repo Oluşturma Rehberi"
echo "======================================"
echo ""
echo "1️⃣  GitHub'da yeni repo oluştur:"
echo "   - https://github.com/new"
echo "   - Repo adı: tiktok-banking-ad-scraper (veya istediğin isim)"
echo "   - README, .gitignore, license EKLEME!"
echo ""
echo "2️⃣  Repo oluşturulduktan sonra bu script'i çalıştır:"
echo ""
read -p "GitHub kullanıcı adınızı girin: " GITHUB_USER
read -p "Yeni repo adını girin: " REPO_NAME

echo ""
echo "🔗 Remote'u güncelliyorum..."
git remote remove origin 2>/dev/null
git remote add origin https://github.com/${GITHUB_USER}/${REPO_NAME}.git

echo ""
echo "✅ Remote güncellendi!"
echo ""
echo "3️⃣  Şimdi push yap:"
echo "   git push -u origin main"
echo ""
read -p "Şimdi push yapmak ister misin? (y/n): " PUSH_NOW

if [ "$PUSH_NOW" = "y" ] || [ "$PUSH_NOW" = "Y" ]; then
    echo ""
    echo "📤 Push yapılıyor..."
    git push -u origin main
    echo ""
    echo "✅ Tamamlandı! Railway'de yeni repo'yu deploy edebilirsin."
else
    echo ""
    echo "⏭️  Push'u daha sonra yapabilirsin:"
    echo "   git push -u origin main"
fi
