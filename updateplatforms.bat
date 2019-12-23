sgutil.py --file svngitmigration.txt --xml-file platforms\ComponentsVersions_4_5_3.xml --export-platforms --nohttps
sgutil.py --file svngitmigration.txt --xml-file platforms\ComponentsVersions_4_5_2.xml --export-platforms --nohttps
sgutil.py --file svngitmigration.txt --xml-file platforms\ComponentsVersions_4_5_1.xml --export-platforms --nohttps
sgutil.py --file svngitmigration.txt --xml-file platforms\ComponentsVersions_4_5_0.xml --export-platforms --nohttps
sgutil.py --file svngitmigration.txt --xml-file platforms\ComponentsVersions_4_2_0.xml --export-platforms --nohttps
sgutil.py --file svngitmigration.txt --xml-file platforms\ComponentsVersions_4_0_1.xml --export-platforms --nohttps
git pull
git add platforms/*
git commit -m "Automatic ABM commit for Platforms"
git push 