sgutil.py --file svngitmigration.txt --xml-file platforms\ComponentsVersions_4_5_3.xml --platform 4_5_3--export-platforms --nohttps
rem sgutil.py --file svngitmigration.txt --xml-file platforms\ComponentsVersions_4_5_2.xml --platform 4_5_2 --export-platforms --nohttps
sgutil.py --file svngitmigration.txt --xml-file platforms\ComponentsVersions_4_5_1.xml --platform 4_5_1 --export-platforms --nohttps
sgutil.py --file svngitmigration.txt --xml-file platforms\ComponentsVersions_4_5_0.xml --platform 4_5_0 --export-platforms --nohttps
sgutil.py --file svngitmigration.txt --xml-file platforms\ComponentsVersions_4_2_0.xml --platform 4_2_0 --export-platforms --nohttps
sgutil.py --file svngitmigration.txt --xml-file platforms\ComponentsVersions_4_1_0.xml --platform 4_1_0 --export-platforms --nohttps
git pull
git add platforms/*
git commit -m "Automatic ABM commit for Platforms"
git push 