"""Bổ sung bài viết có ảnh thật cho cổng thông tin.

Ảnh lấy từ Wikimedia Commons (giấy phép mở: CC0, CC BY, CC BY-SA, phạm vi công cộng). Tác giả và giấy
phép của từng ảnh được ghi ở cuối bài, đúng yêu cầu của giấy phép. Nếu không tải được ảnh (mất mạng)
thì dùng ảnh đại diện vẽ tự động như bộ bài gốc.

    python manage.py seed_content           # chạy trước để có chuyên mục
    python manage.py seed_more_content
    python manage.py seed_more_content --force   # ghi đè bài đã có

Chạy lại nhiều lần vẫn an toàn: bài định danh bằng slug.
"""
import html
import io
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.management.commands.seed_content import SEED_NOTE, render_cover

API = "https://commons.wikimedia.org/w/api.php"
UA = "BVTV-portal-seed/1.0 (admin@example.local)"

ARTICLES = [
    {
        "slug": "phong-tru-oc-buou-vang-hai-lua-gieo-cay",
        "title": "Phòng trừ ốc bươu vàng hại lúa mới gieo cấy: bắt sớm, giữ nước nông, chặn ở cửa mương",
        "type": "advice", "category": "huong-dan", "days_ago": 2, "views": 1480, "featured": True,
        "image": "File:Golden apple snail (Pomacea canaliculata) ,Eichhornia crassipes, China.jpg",
        "summary": "Ốc bươu vàng gây hại mạnh nhất trên lúa trong 2–3 tuần đầu sau gieo cấy. Bắt ốc và ổ trứng, giữ nước nông, chắn lưới ở cửa nước là ba biện pháp rẻ và hiệu quả nhất.",
        "content": """## Vì sao cần phòng trừ sớm

Ốc bươu vàng (*Pomacea canaliculata*) ăn thân và lá non của lúa, có thể làm mất mạ trên cả thửa chỉ sau vài đêm. Thời kỳ nguy hiểm nhất là từ khi gieo sạ hoặc cấy đến khoảng 2–3 tuần sau, khi cây còn nhỏ và mềm. Lúa đã đẻ nhánh rộ và thân cứng thì ốc ít gây hại hơn.

## Các biện pháp nên làm

### 1. Bắt ốc và thu ổ trứng

- Bắt ốc vào sáng sớm hoặc chiều mát, lúc ốc bò lên cạn hoặc bám trên cây.
- Ổ trứng có màu hồng tươi, bám trên thân lúa, cọc, bờ ruộng. Thu và đập nát ổ trứng trước khi nở.
- Làm đều nhiều ngày liên tiếp, không bắt một lần rồi bỏ.

### 2. Điều tiết nước

Sau gieo cấy giữ nước ruộng ở mức 2–3 cm, rút nước nông ở những ngày đầu để ốc khó di chuyển và dễ bắt. Không để nước sâu kéo dài ở giai đoạn lúa còn nhỏ.

### 3. Chặn ốc từ ngoài vào

Đặt lưới hoặc rọ chắn ở cửa lấy nước vào ruộng. Cắm cọc tre, que nhỏ ở nơi ốc thường đến để ốc đẻ trứng vào đó, rồi thu gom.

### 4. Dùng thuốc khi thật cần

Chỉ dùng thuốc trừ ốc có trong danh mục được phép, đúng liều và đúng cách ghi trên nhãn. Thuốc có thể gây hại cho cá, tôm và thủy sinh trong ruộng, nên tránh dùng ở nơi có nuôi cá kết hợp hoặc gần nguồn nước sinh hoạt.

> Phòng trừ ốc hiệu quả nhất khi cả cánh đồng cùng làm một lúc. Một thửa làm tốt nhưng thửa bên cạnh bỏ mặc thì ốc vẫn tràn sang.

## Lưu ý an toàn

Ốc có thể mang ký sinh trùng. Dùng găng tay khi bắt, không ăn ốc sống hoặc nấu chưa chín.""",
    },
    {
        "slug": "phong-tru-chuot-hai-lua-bang-bien-phap-tong-hop",
        "title": "Phòng trừ chuột hại lúa: làm đồng loạt cả cánh đồng, giữ bờ ruộng gọn sạch",
        "type": "guide", "category": "huong-dan", "days_ago": 3, "views": 1235, "featured": False,
        "image": "File:Field rats infesting rice plants (11058917815).jpg", "focus": 0.35,
        "summary": "Chuột sinh sản mạnh từ giai đoạn lúa làm đòng. Hiệu quả cao nhất khi cả xã đồng cùng diệt chuột, kết hợp vệ sinh đồng ruộng, bẫy và hạn chế nơi trú ẩn.",
        "content": """## Đặc điểm cần biết

Chuột đồng (điển hình là chuột *Rattus argentiventer*) ăn lúa từ giai đoạn đẻ nhánh đến chín. Chúng bắt đầu sinh sản mạnh khi lúa làm đòng, nên số lượng tăng nhanh ở cuối vụ. Chuột chuyển chỗ ở theo mùa vụ: sau thu hoạch về bờ bao, gò đất, khu dân cư; khi lúa lên thì ra ruộng.

## Biện pháp tổng hợp

### Vệ sinh đồng ruộng

- Phát quang cỏ dại, dọn rơm rạ và đống rác ven bờ ruộng, bờ mương.
- Đắp bờ nhỏ gọn (thấp và hẹp), hạn chế hang hốc.
- Gieo cấy tập trung, cùng thời điểm để lúa trổ đồng loạt, chuột thiếu thức ăn kéo dài.

### Diệt chuột trực tiếp

- Đào hang, đặt bẫy, bẫy lồng ở các lối chuột hay đi.
- Tổ chức đợt diệt chuột đồng loạt theo thôn, xã vào đầu vụ và khi lúa làm đòng.
- Bảo vệ thiên địch: rắn, cú mèo, chó, mèo. Dựng cọc cho chim cú đậu ở ruộng.

### Dùng bả

Chỉ dùng thuốc diệt chuột đã được phép lưu hành, đặt có kiểm soát, đánh dấu để người và gia súc biết. Thu gom xác chuột và bả thừa, không để trẻ em hay vật nuôi tiếp xúc.

> Diệt chuột một nhà một ruộng ít hiệu quả. Cần phối hợp cả cánh đồng, và duy trì đều cả năm, không chỉ khi chuột đã gây hại.

## Theo dõi

Cán bộ điều tra ghi nhận số hang hoạt động và tỷ lệ dảnh bị cắt trong phiếu điều tra để cảnh báo sớm cho các hộ liền kề.""",
    },
    {
        "slug": "sau-to-hai-rau-ho-thap-tu-quan-ly-khang-thuoc",
        "title": "Sâu tơ hại rau họ thập tự: luân phiên hoạt chất để hạn chế kháng thuốc",
        "type": "advice", "category": "huong-dan", "days_ago": 4, "views": 980, "featured": False,
        "image": "File:Plutella xylostella (Diamondback moth), Giethoorn, the Netherlands.jpg",
        "summary": "Sâu tơ là sâu hại chính trên bắp cải, su hào, cải xanh và dễ kháng thuốc. Luân phiên nhóm thuốc, dùng chế phẩm sinh học và bảo vệ thiên địch giúp giữ hiệu lực phòng trừ.",
        "content": """## Tình hình

Sâu tơ (*Plutella xylostella*) là loài sâu hại chính trên rau họ thập tự như bắp cải, súp lơ, cải xanh, cải ngọt. Sâu non ăn biểu bì và thịt lá, để lại những vết khuyết trong như cửa sổ, nặng thì lá chỉ còn gân. Vòng đời ngắn nên số thế hệ trong năm nhiều, quần thể tăng rất nhanh trong thời tiết khô nóng.

## Vì sao khó trị

Sâu tơ nổi tiếng là loài dễ kháng thuốc: phun nhiều lần cùng một loại thuốc sẽ làm giảm hiệu lực nhanh. Tăng liều hay trộn nhiều thuốc không giải quyết được mà làm tăng chi phí, tồn dư và giết thiên địch.

## Cách quản lý

1. **Luân phiên nhóm hoạt chất** theo cơ chế tác động khác nhau giữa các lần phun, không dùng một nhóm quá hai lần liền trong một vụ.
2. **Dùng chế phẩm sinh học** như *Bacillus thuringiensis* ở giai đoạn sâu tuổi nhỏ.
3. **Bảo vệ thiên địch**, trong đó có ong ký sinh sâu non. Hạn chế thuốc phổ rộng ở giai đoạn đầu vụ.
4. **Luân canh** với cây không thuộc họ thập tự (hành, cà chua, đậu) sau mỗi 1–2 vụ.
5. **Vệ sinh đồng ruộng**: thu dọn tàn dư, lá già sau thu hoạch, tiêu hủy cây bị hại nặng.
6. **Tưới phun mưa** hoặc phun nước vào chiều mát có thể làm giảm trưởng thành đẻ trứng.

> Phun khi sâu đạt ngưỡng chứ không phun theo lịch. Kiểm tra ruộng 2–3 lần mỗi tuần, đếm sâu trên mẫu cây.

## Thời gian cách ly

Tuân thủ thời gian cách ly ghi trên nhãn. Rau ăn lá thu hoạch liên tục càng cần chọn thuốc có thời gian cách ly ngắn.""",
    },
    {
        "slug": "ruoi-duc-qua-tren-cay-an-qua-bien-phap-an-toan",
        "title": "Ruồi đục quả hại cây ăn quả: bẫy dẫn dụ, bao quả và thu gom quả rụng",
        "type": "guide", "category": "huong-dan", "days_ago": 5, "views": 1102, "featured": False,
        "image": "File:Mango fruit fly (Bactrocera dorsalis).jpg",
        "summary": "Ruồi đục quả đẻ trứng vào quả chín, dòi làm quả thối và rụng. Bẫy dẫn dụ ruồi đực, bao quả và thu gom quả rụng là bộ ba biện pháp ít dùng thuốc.",
        "content": """## Triệu chứng

Ruồi đục quả (*Bactrocera dorsalis* và nhóm Bactrocera) đẻ trứng vào vỏ quả khi quả bắt đầu chín. Dòi nở ra ăn thịt quả, vết đục có mủ hoặc chảy nước, quả mềm nhũn, thối và rụng sớm. Hại trên xoài, ổi, thanh long, mận, cam, bưởi và nhiều cây khác.

## Biện pháp phòng trừ

### Bẫy dẫn dụ

Dùng bẫy có chất dẫn dụ ruồi đực (methyl eugenol) đặt cao khoảng 1,5 m, mật độ theo hướng dẫn của sản phẩm. Thay chất dẫn dụ đúng định kỳ. Số ruồi bắt được cũng là chỉ báo để biết ruồi đang nhiều hay ít.

### Bao quả

Bao quả bằng giấy hoặc túi lưới chuyên dụng từ khi quả còn nhỏ, trước khi ruồi đẻ. Cách này vừa giảm ruồi, vừa giảm thuốc, quả đẹp, dễ bán giá cao.

### Vệ sinh vườn

- Nhặt toàn bộ quả rụng và quả bị hại hàng ngày hoặc cách ngày.
- Cho vào túi nilon buộc kín để phơi nắng, hoặc chôn sâu. Không vứt ra mương hay gốc cây.
- Tỉa cành thông thoáng, làm sạch cỏ dưới tán.

### Dùng thuốc

Chỉ phun bả protein hoặc thuốc trong danh mục, theo hướng dẫn, và giữ đúng thời gian cách ly trước thu hoạch.

> Cần phối hợp cả khu vườn, thậm chí cả vùng trồng. Một vườn bỏ hoang không thu quả rụng là nguồn ruồi cho các vườn xung quanh.

## Yêu cầu đối với hàng xuất khẩu

Vùng trồng xuất khẩu thường phải có chương trình giám sát ruồi đục quả bằng bẫy theo định kỳ. Lưu hồ sơ theo dõi bẫy để phục vụ truy xuất.""",
    },
    {
        "slug": "thien-dich-ban-dong-hanh-cua-nguoi-trong-lua",
        "title": "Thiên địch ngoài đồng: bọ rùa, nhện, ong ký sinh và cách giữ chúng ở lại ruộng",
        "type": "guide", "category": "huong-dan", "days_ago": 6, "views": 870, "featured": False,
        "image": "File:Ladybird and aphids.JPG",
        "summary": "Bọ rùa, nhện, bọ xít bắt mồi và ong ký sinh tự kiềm chế nhiều loài sâu rầy hại. Không phun thuốc phổ rộng sớm và giữ cây hoa ven bờ là cách giữ lực lượng này.",
        "content": """## Thiên địch là gì

Thiên địch là các sinh vật ăn hoặc ký sinh sâu rầy hại cây trồng. Ngoài đồng, nhóm thường gặp gồm:

- **Bọ rùa** ăn rệp, rầy mềm. Cả ấu trùng và trưởng thành đều bắt mồi.
- **Nhện** săn mồi giăng lưới hoặc rình mồi, ăn rầy, sâu non nhỏ.
- **Bọ xít mù xanh, bọ xít bắt mồi** ăn trứng rầy.
- **Ong ký sinh** đẻ trứng vào trứng hoặc sâu non của sâu hại, ví dụ ong ký sinh trứng sâu cuốn lá, sâu đục thân.
- **Chuồn chuồn, kiến, bọ cánh cứng ăn sâu** cũng góp phần đáng kể.

## Vì sao cần giữ

Khi thiên địch đủ, nhiều đợt rầy hay sâu non không kịp tăng thành dịch. Ngược lại, phun thuốc phổ rộng sớm làm thiên địch chết trước, sâu rầy hại bùng lên mạnh sau đó, buộc phải phun thêm.

## Làm gì để giữ thiên địch

1. **Không phun thuốc trừ sâu trong khoảng 40 ngày đầu sau gieo sạ** nếu không có lý do thật sự. Đây là nội dung quen thuộc của chương trình IPM trên lúa.
2. **Phun theo ngưỡng** sau khi đếm sâu rầy và thiên địch trên ruộng, không phun theo lịch.
3. **Chọn thuốc chọn lọc** khi buộc phải phun, tránh thuốc phổ rộng.
4. **Trồng hoa ven bờ** (cúc, vạn thọ, các loài hoa nhỏ) làm nơi trú ẩn và nguồn mật cho ong ký sinh.
5. **Giữ cỏ bờ** ở mức vừa phải, không dọn trọc, để thiên địch có chỗ ở.

> Một quy tắc dễ nhớ: nhìn kỹ trước khi phun. Nếu số thiên địch tương đương hoặc nhiều hơn số sâu hại thì thường chưa cần phun.""",
    },
    {
        "slug": "sau-duc-than-lua-nhan-biet-ngon-heo-bong-bac",
        "title": "Sâu đục thân hại lúa: nhận biết ngọn héo và bông bạc, thu ổ trứng sớm",
        "type": "situation", "category": "ban-tin", "days_ago": 8, "views": 1310, "featured": False,
        "image": "File:Rice yellow stem borer.jpg",
        "summary": "Sâu đục thân gây hai triệu chứng đặc trưng: ngọn héo ở giai đoạn đẻ nhánh và bông bạc ở giai đoạn trổ. Thu ổ trứng, bẫy đèn và gieo cấy tập trung giúp giảm mật độ.",
        "content": """## Nhận biết

Sâu đục thân hai chấm và sâu đục thân bướm vàng (*Scirpophaga incertulas*) hại lúa trên khắp các vùng trồng. Sâu non đục vào thân cây lúa, ăn mô bên trong.

- **Giai đoạn đẻ nhánh:** lá bẹ giữa héo vàng, rút nhẹ thì kéo ra được. Gọi là *ngọn héo*.
- **Giai đoạn làm đòng đến trổ:** bông không hạt, trắng, đứng thẳng. Gọi là *bông bạc*.

Bướm đẻ trứng thành từng ổ trên lá, ổ phủ lớp lông màu vàng nâu.

## Việc cần làm

1. **Thu và hủy ổ trứng** khi đi thăm đồng. Đặt ổ trứng vào lọ thả ngoài ruộng để ong ký sinh vẫn bay ra được, nhưng bướm không thoát.
2. **Gieo cấy tập trung** cùng thời điểm, giãn cách thời vụ hợp lý để cắt đứt thức ăn của sâu.
3. **Bẫy đèn** vào các đợt bướm rộ để theo dõi và giảm số lượng.
4. **Xử lý rơm rạ gốc rạ** sau thu hoạch: cày vùi, ngâm nước để tiêu diệt sâu trú trong gốc.
5. **Bảo vệ ong ký sinh** và các thiên địch khác, không phun thuốc phổ rộng không cần thiết.
6. **Phun thuốc khi mật độ ổ trứng đạt ngưỡng** theo khuyến cáo địa phương, vào đúng lúc sâu non mới nở.

> Sau khi đã thấy bông bạc thì thuốc không còn cứu được bông đó. Thời điểm xử lý hiệu quả là khi bướm rộ và sâu non mới nở.

## Ghi nhận trong phiếu điều tra

Ghi tỷ lệ dảnh héo, tỷ lệ bông bạc và số ổ trứng trên một mét vuông để hệ thống tính mức độ gây hại và đề xuất cảnh báo.""",
    },
    {
        "slug": "rep-sap-bot-hong-tren-san-ong-ky-sinh-anagyrus",
        "title": "Rệp sáp bột hồng hại sắn và vai trò của ong ký sinh trong phòng trừ sinh học",
        "type": "guide", "category": "huong-dan", "days_ago": 9, "views": 640, "featured": False,
        "image": "File:Anagyrus lopezi.jpg",
        "summary": "Rệp sáp bột hồng làm ngọn sắn xoăn, còi cọc và giảm năng suất. Ngoài vệ sinh hom giống, nhiều nước dùng ong ký sinh Anagyrus lopezi để kiềm chế loài này.",
        "content": """## Triệu chứng

Rệp sáp bột hồng (*Phenacoccus manihoti*) chích hút nhựa ở ngọn và lá non của sắn. Ngọn xoăn, lá co rúm, đốt thân ngắn lại, cây còi cọc, củ nhỏ. Rệp phủ lớp sáp trắng như bột, dễ nhìn thấy ở nõn.

## Cách lây lan

Rệp lan chủ yếu qua hom giống nhiễm, qua phương tiện vận chuyển, dụng cụ và theo gió ở quãng ngắn. Vì thế quản lý hom giống là khâu quan trọng nhất.

## Biện pháp

1. **Chọn hom sạch.** Chỉ lấy hom từ ruộng không có rệp. Kiểm tra kỹ, loại bỏ hom có dấu hiệu nhiễm trước khi trồng.
2. **Xử lý hom** theo hướng dẫn của cơ quan chuyên môn trước khi trồng.
3. **Kiểm tra ruộng thường xuyên** nhất là vụ khô, khi rệp phát triển mạnh. Cắt bỏ và tiêu hủy ngọn bị hại khi mới xuất hiện ổ nhỏ.
4. **Không vận chuyển sắn** từ vùng đang có dịch sang vùng chưa có khi chưa kiểm dịch.
5. **Phòng trừ sinh học.** Ong ký sinh *Anagyrus lopezi* là thiên địch chuyên tính của loài rệp này, đã được nhiều nước trồng sắn nhân thả để kiềm chế rệp lâu dài. Việc nhân thả cần do cơ quan chuyên môn hướng dẫn, nông dân không tự ý du nhập.
6. **Hạn chế thuốc phổ rộng** vì sẽ làm chết thiên địch.

> Phòng trừ sinh học cho kết quả chậm hơn thuốc hóa học nhưng bền vững hơn, chi phí thấp hơn về lâu dài.

## Báo cáo

Khi thấy rệp ở vùng chưa từng ghi nhận, báo ngay trạm BVTV địa phương để khoanh vùng và xử lý kịp thời.""",
    },
    {
        "slug": "an-toan-khi-phun-thuoc-bao-ve-thuc-vat",
        "title": "An toàn khi phun thuốc bảo vệ thực vật: trang bị, thời điểm và xử lý bao bì",
        "type": "notice", "category": "thong-bao", "days_ago": 10, "views": 1560, "featured": False,
        "image": "File:Vegetable farmer.jpg", "focus": 0.4,
        "summary": "Nhắc lại các nguyên tắc bảo hộ cho người phun thuốc: đồ bảo hộ đầy đủ, tránh phun lúc nắng gắt hoặc ngược gió, thu gom và xử lý vỏ bao bì đúng nơi quy định.",
        "content": """## Trước khi phun

- Đọc kỹ nhãn: tên thuốc, liều, đối tượng, thời gian cách ly, biện pháp an toàn.
- Kiểm tra bình, vòi phun, ống dẫn, không để rò rỉ.
- Chuẩn bị đủ nước sạch và xà phòng để rửa tay, rửa mặt khi cần.

## Trang bị bảo hộ

Người phun cần đeo khẩu trang chuyên dụng, kính, găng tay, mặc áo dài tay, quần dài, đi ủng. Không mặc quần áo đã dính thuốc để ra ngoài, giặt riêng sau khi phun.

## Khi phun

1. Phun lúc trời mát (sáng sớm hoặc chiều muộn), tránh nắng gắt và lúc gió mạnh.
2. **Đi thuận chiều gió**, không đi ngược gió để thuốc bay vào người.
3. Không ăn, uống, hút thuốc khi đang phun.
4. Không phun khi trời sắp mưa.
5. Giữ khoảng cách với nhà dân, ao cá, nguồn nước sinh hoạt.
6. Không để trẻ em và vật nuôi ở gần.

## Sau khi phun

- Tắm và thay quần áo ngay.
- **Súc rửa bình phun xa nguồn nước**, không đổ thuốc thừa xuống ao hồ, mương.
- **Thu gom vỏ chai, bao bì** vào thùng thu gom quy định, không vứt ra ruộng hay đốt tùy tiện.
- Cắm biển cảnh báo ruộng vừa phun và tuân thủ thời gian cách ly trước khi thu hoạch.

## Khi có dấu hiệu ngộ độc

Chóng mặt, buồn nôn, vã mồ hôi, co giật hoặc khó thở là dấu hiệu cần xử lý khẩn cấp. Đưa người bệnh ra nơi thoáng, cởi bỏ quần áo dính thuốc, rửa sạch da, rồi **đưa ngay tới cơ sở y tế gần nhất**, mang theo nhãn thuốc hoặc vỏ chai để bác sĩ biết hoạt chất.

> Thuốc BVTV là công cụ cuối cùng trong chương trình IPM. Dùng đúng, dùng đủ và bảo hộ đầy đủ là bảo vệ chính người phun và người tiêu dùng.""",
    },
    {
        "slug": "xu-ly-rom-ra-va-goc-ra-sau-thu-hoach-vu-lua",
        "title": "Xử lý rơm rạ và gốc rạ sau thu hoạch: giảm nguồn sâu bệnh cho vụ sau",
        "type": "news", "category": "tin-tuc", "days_ago": 12, "views": 720, "featured": False,
        "image": "File:Duck herding in harvested rice field, Vietnam.jpg",
        "summary": "Rơm rạ và gốc rạ là nơi trú ẩn của sâu đục thân, rầy và mầm bệnh. Cày vùi, ngâm nước, chăn thả vịt hoặc ủ phân giúp giảm nguồn sâu bệnh và tận dụng rơm.",
        "content": """## Vì sao phải xử lý

Sau thu hoạch, gốc rạ và rơm còn sót là nơi sâu đục thân qua đông, mầm bệnh (như bệnh đạo ôn, khô vằn) tồn tại, và là chỗ cư trú cho chuột. Cỏ dại và lúa chét mọc lên làm cầu nối sâu bệnh sang vụ sau.

## Các cách xử lý

### Cày vùi và ngâm nước

Cày lật gốc rạ rồi ngâm nước một thời gian giúp tiêu diệt sâu non trong gốc và giúp rơm mục nhanh hơn.

### Chăn thả vịt

Thả vịt vào ruộng sau thu hoạch là cách truyền thống ở nhiều vùng: vịt ăn rụng lúa, ốc bươu vàng, côn trùng, cào xới đất. Cần phối hợp thời gian cho vịt chạy đồng, tránh nơi mới phun thuốc và theo dõi dịch cúm gia cầm tại địa phương.

### Ủ rơm làm phân hoặc chất độn

Rơm ủ cùng chế phẩm vi sinh trở thành phân hữu cơ. Có thể dùng làm giá thể trồng nấm, thức ăn cho gia súc hoặc phủ gốc cây.

### Không đốt rơm

Đốt rơm ngoài đồng gây khói bụi, ảnh hưởng sức khỏe và giao thông, làm mất chất hữu cơ và tiêu diệt cả thiên địch trong đất. Nên hạn chế và hướng dẫn bà con chuyển sang các cách dùng rơm ở trên.

## Kết hợp với các biện pháp khác

- Phát quang cỏ bờ, vệ sinh bờ ruộng, bờ mương.
- Giãn cách thời vụ giữa hai vụ để cắt nguồn thức ăn của sâu rầy.
- Làm đất kỹ trước khi gieo vụ mới.

> Vệ sinh đồng ruộng sau thu hoạch là việc tốn ít công nhưng giảm đáng kể áp lực sâu bệnh cho vụ sau.""",
    },
    {
        "slug": "theo-doi-san-xuat-lua-vung-cao-mua-thu-hoach",
        "title": "Sản xuất lúa vùng cao đến mùa thu hoạch: lưu ý phòng ẩm mốc và hao hụt",
        "type": "news", "category": "tin-tuc", "days_ago": 14, "views": 590, "featured": False,
        "image": "File:Road and paddy fields in Sa Pa, Vietnam, 20240126 1202 3586.jpg",
        "summary": "Ở vùng ruộng bậc thang, lúa chín dồn trong thời gian ngắn. Cần thu hoạch đúng lúc, phơi sấy kịp thời và bảo quản khô ráo để hạn chế hao hụt và mốc.",
        "content": """## Bối cảnh

Ruộng bậc thang vùng núi canh tác chủ yếu một vụ lúa mỗi năm, lúa chín tập trung trong khoảng thời gian ngắn. Địa hình dốc, đường vận chuyển hẹp khiến khâu thu hoạch và phơi sấy thường là điểm nghẽn.

## Khuyến cáo thu hoạch

- Thu hoạch khi khoảng 85–90% số hạt trên bông đã chín vàng. Gặt quá sớm làm nhiều hạt lép xanh, gặt quá muộn làm rụng hạt và gãy bông.
- Tránh gặt khi mưa. Lúa ướt phải được phơi hoặc sấy ngay, không chất đống qua đêm.
- Tuốt hạt càng sớm càng tốt sau khi cắt.

## Phơi sấy và bảo quản

1. Phơi trên sân sạch, bạt hoặc nia, trở thường xuyên để hạt khô đều.
2. Độ ẩm hạt khi cất kho nên ở mức khoảng 13–14%.
3. Dùng bao, thùng, bồ kín, đặt trên giá kê cao, cách tường, thoáng và khô.
4. Kiểm tra định kỳ để phát hiện mọt, mốc và chuột sớm.
5. Lúa giống để riêng, chọn bông tốt, phơi kỹ và bảo quản kín.

## Gắn với phòng trừ dịch hại

Sau thu hoạch, dọn vệ sinh ruộng, xử lý rơm rạ và gốc rạ để không tạo nguồn sâu bệnh cho vụ sau. Cán bộ BVTV cập nhật kết quả điều tra cuối vụ để chuẩn bị khuyến cáo cho vụ tới.

> Mất mùa không chỉ do sâu bệnh ngoài đồng. Hao hụt sau thu hoạch có thể làm mất một phần đáng kể sản lượng nếu bảo quản kém.""",
    },
]


def _clean(text):
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def fetch_image(title):
    """Trả về (bytes ảnh, dòng ghi nguồn) hoặc (None, None) nếu không tải được."""
    q = urllib.parse.urlencode({"action": "query", "format": "json", "titles": title, "prop": "imageinfo",
                                "iiprop": "url|extmetadata", "iiurlwidth": 1400})
    headers = {"User-Agent": UA}
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{API}?{q}", headers=headers), timeout=30) as r:
                pages = json.load(r)["query"]["pages"]
            info = next(iter(pages.values())).get("imageinfo")
            if not info:
                return None, None
            info = info[0]
            with urllib.request.urlopen(urllib.request.Request(info["thumburl"], headers=headers), timeout=60) as r:
                data = r.read()
            meta = info.get("extmetadata", {})
            author = _clean(meta.get("Artist", {}).get("value")) or "Không rõ tác giả"
            lic = _clean(meta.get("LicenseShortName", {}).get("value")) or "giấy phép mở"
            page = "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
            return data, f"Ảnh: {author[:120]}, giấy phép {lic}, nguồn Wikimedia Commons: {page}"
        except Exception:  # noqa: BLE001
            time.sleep(2 * (attempt + 1))
    return None, None


def to_cover(data, focus=0.5):
    from PIL import Image

    img = Image.open(io.BytesIO(data)).convert("RGB")
    w, h = img.size
    target = 2.0
    if w / h > target:
        nw = int(h * target)
        left = (w - nw) // 2
        img = img.crop((left, 0, left + nw, h))
    else:
        nh = int(w / target)
        top = max(0, min(h - nh, int(h * focus - nh / 2)))
        img = img.crop((0, top, w, top + nh))
    img = img.resize((1200, 600))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=84, optimize=True)
    return ContentFile(buf.getvalue())


class Command(BaseCommand):
    help = "Thêm bài viết có ảnh thật (Wikimedia Commons, giấy phép mở) vào cổng thông tin."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Ghi đè bài đã có.")

    @transaction.atomic
    def handle(self, *args, **opts):
        from accounts.models import User
        from cms import insights
        from cms.models import Category, Post, PostRevision

        now = timezone.now()
        author = User.objects.filter(role="editor").first()
        approver = User.objects.filter(role="approver").first()
        cats = {c.slug: c for c in Category.objects.all()}
        created = skipped = no_photo = 0
        for index, spec in enumerate(ARTICLES):
            post = Post.objects.filter(slug=spec["slug"]).first()
            if post and not opts["force"]:
                skipped += 1
                continue
            data, credit = fetch_image(spec["image"])
            # core.textfmt chỉ hỗ trợ chữ đậm, nên bỏ dấu * của chữ nghiêng (tên khoa học).
            content = re.sub(r"(?<!\*)\*(?!\*)([^*\n]+?)(?<!\*)\*(?!\*)", r"\1", spec["content"].strip())
            if credit:
                content += f"\n\n## Nguồn ảnh\n\n{credit}"
            defaults = {
                "title": spec["title"], "post_type": spec["type"], "category": cats.get(spec["category"]),
                "summary": spec["summary"], "content": content, "status": "published",
                "is_featured": spec["featured"], "published_at": now - timedelta(days=spec["days_ago"], hours=index + 2),
                "author": author, "reviewed_by": approver, "review_note": "Duyệt nội dung chuyên ngành.",
                "views": spec["views"], "version": 1,
            }
            if post:
                for k, v in defaults.items():
                    setattr(post, k, v)
                post.save()
            else:
                post = Post.objects.create(slug=spec["slug"], **defaults)
                PostRevision.objects.create(post=post, version=1, action="create", title=post.title,
                                            content=post.content, note=SEED_NOTE, user=author)
                created += 1
            if data:
                post.cover.save(f"{spec['slug']}.jpg", to_cover(data, spec.get("focus", 0.5)), save=True)
                self.stdout.write(f"  ảnh thật: {spec['slug']}")
            else:
                no_photo += 1
                post.cover.save(f"{spec['slug']}.jpg", render_cover("Hướng dẫn kỹ thuật", spec["title"], spec["type"], index + 40), save=True)
                self.stdout.write(self.style.WARNING(f"  không tải được ảnh, dùng ảnh vẽ: {spec['slug']}"))
            time.sleep(1)
        insights.refresh_hot_scores()
        self.stdout.write(self.style.SUCCESS(f"Xong: {created} bài mới, {skipped} bài đã có, {no_photo} bài dùng ảnh vẽ."))
