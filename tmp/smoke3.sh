#!/bin/bash
# Smoke test for transfers, old gold billing and lookbook (run against local backend)
A=http://localhost:8001/api
J="Content-Type: application/json"
tok() { curl -s -X POST $A/auth/login -H "$J" -d "{\"email\":\"$1\",\"password\":\"$2\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])"; }
T=$(tok admin@swarnaerp.in Admin@12345); H="Authorization: Bearer $T"
BR=$(curl -s $A/branches -H "$H")
BZ=$(echo "$BR" | python3 -c "import sys,json;print([b['id'] for b in json.load(sys.stdin) if b['code']=='ZB-MAIN'][0])")
BB=$(echo "$BR" | python3 -c "import sys,json;print([b['id'] for b in json.load(sys.stdin) if b['code']=='MG-BLR'][0])")
CAT=$(curl -s $A/categories -H "$H" | python3 -c "import sys,json;print(json.load(sys.stdin)[1]['id'])")
P22=$(curl -s $A/purities -H "$H" | python3 -c "import sys,json;print([p['id'] for p in json.load(sys.stdin) if p['code']=='22K916'][0])")
S=$RANDOM
mk() { curl -s -X POST $A/items -H "$H" -H "$J" -d "{\"tag_id\":\"$1\",\"category_id\":\"$CAT\",\"purity_id\":\"$P22\",\"gross_wt\":$2,\"stone_wt\":0.5,\"making_charge_type\":\"percent\",\"making_charge_value\":12,\"branch_id\":\"$BZ\",\"description\":\"$3\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])"; }
I1=$(mk "NK-$S-1" 24.5 "Temple Necklace"); I2=$(mk "NK-$S-2" 8.2 "Floral Jhumka"); I3=$(mk "NK-$S-3" 5.1 "Kada")
echo "items $I1 $I2 $I3"
python3 -c "
from PIL import Image, ImageDraw
im=Image.new('RGB',(800,800),'#7a5a1a'); d=ImageDraw.Draw(im); d.ellipse([150,150,650,650],outline='#f0d080',width=40); im.save('/app/tmp/ring.png')"
curl -s -X POST $A/files -H "$H" -F owner_type=item -F owner_id=$I1 -F file=@/app/tmp/ring.png -o /dev/null -w "photo upload %{http_code}\n"
echo "--- lookbook"
LB=$(curl -s -X POST $A/lookbook -H "$H" -H "$J" -d "{\"branch_id\":\"$BZ\",\"title\":\"Bridal Collection 2026\",\"subtitle\":\"Now at Zaveri Bazar\",\"item_ids\":[\"$I1\",\"$I2\",\"$I3\"]}")
echo "$LB" | head -c 300; echo
LID=$(echo "$LB" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])"); FID=$(echo "$LB" | python3 -c "import sys,json;print(json.load(sys.stdin)['file_id'])")
curl -s $A/files/$FID/download -H "$H" -o /app/tmp/card.png -w "card download %{http_code}\n"
curl -s -X POST $A/lookbook/$LID/broadcast -H "$H" -H "$J" -d '{"message":"New bridal collection","audience":"custom","phones":["9876500001","123"]}'; echo
echo "--- old gold bill"
curl -s -X POST $A/bills/quote -H "$H" -H "$J" -d "{\"branch_id\":\"$BZ\",\"item_ids\":[\"$I3\"],\"old_gold\":[{\"description\":\"Old chain\",\"fineness\":0.916,\"gross_wt\":4.0,\"stone_wt\":0.2,\"deduction_pct\":2}]}" | python3 -c "import sys,json;d=json.load(sys.stdin);print({k:d.get(k) for k in ['subtotal','cgst','grand_total','old_gold_total','net_payable']}, d.get('old_gold'))"
B=$(curl -s -X POST $A/bills -H "$H" -H "$J" -d "{\"branch_id\":\"$BZ\",\"item_ids\":[\"$I3\"],\"customer_name\":\"Old Gold Test\",\"old_gold\":[{\"description\":\"Old chain\",\"fineness\":0.916,\"gross_wt\":4.0,\"stone_wt\":0.2,\"deduction_pct\":2}]}")
BIDX=$(echo "$B" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['id'])")
curl -s $A/bills/$BIDX/pdf -H "$H" -o /app/tmp/oldgold.pdf -w "pdf %{http_code}\n"
curl -s "$A/bills/old-gold?branch_id=$BZ" -H "$H" | python3 -c "import sys,json;d=json.load(sys.stdin);print('old gold lots',len(d), d[0]['net_wt'], d[0]['value'])"
curl -s -X POST $A/bills/quote -H "$H" -H "$J" -d "{\"branch_id\":\"$BZ\",\"item_ids\":[\"$I2\"],\"old_gold\":[{\"fineness\":0.999,\"gross_wt\":50}]}"; echo
echo "--- transfer"
TM=$(tok manager.zb@swarnaerp.in Manager@123); HM="Authorization: Bearer $TM"
TC=$(tok counter.blr@swarnaerp.in Counter@123); HC="Authorization: Bearer $TC"
TR=$(curl -s -X POST $A/transfers -H "$HM" -H "$J" -d "{\"from_branch_id\":\"$BZ\",\"to_branch_id\":\"$BB\"}" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['id'])")
curl -s -X POST $A/transfers/$TR/scan-out -H "$HM" -H "$J" -d "{\"code\":\"NK-$S-1\"}" -o /dev/null -w "scan-out1 %{http_code}\n"
curl -s -X POST $A/transfers/$TR/scan-out -H "$HM" -H "$J" -d "{\"code\":\"NK-$S-2\"}" -o /dev/null -w "scan-out2 %{http_code}\n"
curl -s -X POST $A/transfers/$TR/scan-out -H "$HM" -H "$J" -d "{\"code\":\"NK-$S-3\"}" -w " <- sold item scan-out\n"
curl -s -X POST $A/transfers/$TR/dispatch -H "$HM" | python3 -c "import sys,json;d=json.load(sys.stdin);print('dispatched',d['status'],len(d['items']))"
curl -s "$A/items/$I1" -H "$H" | python3 -c "import sys,json;print('item1',json.load(sys.stdin)['status'])"
curl -s -X POST $A/transfers/$TR/scan-in -H "$HC" -H "$J" -d "{\"code\":\"NK-$S-1\"}" -o /dev/null -w "billing user scan-in (expect 403) %{http_code}\n"
curl -s -X POST $A/transfers/$TR/scan-in -H "$H" -H "$J" -d "{\"code\":\"NK-$S-1\"}" -o /dev/null -w "admin scan-in %{http_code}\n"
curl -s -X POST $A/transfers/$TR/scan-in -H "$H" -H "$J" -d '{"code":"RANDOM-XYZ"}' -w " <- unexpected\n"
curl -s -X POST $A/transfers/$TR/receive -H "$H" | python3 -c "import sys,json;d=json.load(sys.stdin);print('received',d['status'],'missing',d['missing_item_ids'],'unexpected',d['unexpected_codes'])"
curl -s "$A/items/$I1" -H "$H" | python3 -c "import sys,json;d=json.load(sys.stdin);print('item1',d['status'],d['branch_id']=='$BB')"
curl -s "$A/items/$I2" -H "$H" | python3 -c "import sys,json;print('item2',json.load(sys.stdin)['status'])"
