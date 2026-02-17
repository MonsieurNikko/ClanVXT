Tổng quan
Hệ thống clan trong server là “chính thống”: clan được bot quản lý, có Captain chịu trách nhiệm, có danh sách thành viên rõ ràng, có lịch sử trận và Elo theo clan.


Elo là Elo của clan, không có Elo cá nhân.


Mọi clan mới tạo đều phải qua Mod duyệt trước khi hoạt động chính thức.



Tài khoản, tham gia clan, và chống lách luật
Mỗi người chỉ được dùng 1 tài khoản Discord để tham gia hệ thống clan.


Dùng nhiều tài khoản để né cooldown, thao túng trận đấu/Elo, hoặc lách luật đều bị coi là gian lận.


Mỗi người chỉ được thuộc 1 clan tại một thời điểm.


Cooldown join/leave clan là 14 ngày. Rời clan hoặc bị kick thì phải chờ đủ 14 ngày mới được vào clan khác.


Ai bị cấm hệ thống clan (system ban) thì không được tạo clan, không được join clan.


Mỗi người sẽ được bot tự động đăng ký danh tính (dựa trên tên Discord) khi tham gia hệ thống clan lần đầu. Phải dùng tài khoản chính, không được dùng smurf. Nếu phát hiện dùng smurf sẽ bị xử phạt.



Quyền hạn trong clan
Captain là người duy nhất được tạo clan và là người chịu trách nhiệm chính.


Captain có thể chỉ định Đội phó (Vice Captain).


Đội phó được dùng các lệnh quản lý clan theo quyền được cấp.


Captain có quyền bổ nhiệm hoặc thu hồi quyền đội phó bất cứ lúc nào.



Điều kiện tạo clan
Captain phải là thành viên đã xác minh (role Verified/Member), không thuộc clan nào, không trong cooldown, không bị system ban.


Khi tạo clan, Captain phải chọn tối thiểu 4 người ngay từ đầu (bạn + 4 = 5 thành viên tổng cộng).


4 người được chọn sẽ nhận lời mời qua DM và phải bấm Đồng ý tham gia (Accept). Không được phép nhét tên người khác nếu họ chưa đồng ý.


Nếu sau 48 giờ không đủ 4 người đồng ý, yêu cầu tạo clan tự hủy.


Tên clan là duy nhất trong server. Không dùng tag.


Không được đặt tên trùng hoặc cố tình nhái gần giống để giả mạo clan khác.


Cấm tên chứa nội dung tục tĩu, kỳ thị, kích động thù hằn, công kích cá nhân, quảng cáo, hoặc gây hiểu nhầm là clan của ban quản trị.



Mod duyệt clan
Clan sau khi đủ 4 Accept sẽ ở trạng thái chờ duyệt.


Mod có quyền Approve/Reject và phải ghi lý do khi từ chối.


Mod có thể từ chối nếu clan có dấu hiệu tạo rác, chiếm tên, gây war, hoặc thành viên có dấu hiệu gian lận.



Role và kênh chat riêng của clan
Khi clan được duyệt và đủ điều kiện hoạt động, bot tự tạo role riêng cho clan và tự gán role đó cho tất cả thành viên clan.


Bot tự tạo kênh chat riêng cho clan. Kênh này chỉ clan và mod xem được.


Nếu clan bị giải tán/ban, kênh sẽ bị khóa hoặc ẩn.



Điều kiện hoạt động của clan
Clan được coi là hoạt động khi có tối thiểu 5 thành viên.


Nếu clan tụt dưới 5 người, clan bị chuyển sang trạng thái không hoạt động và bị khóa các tính năng liên quan đến thi đấu/ghi nhận Elo.



Quản lý thành viên
Member có quyền rời clan bất cứ lúc nào nhưng vẫn chịu cooldown 14 ngày.


Captain có quyền kick thành viên. Kick vẫn áp dụng cooldown 14 ngày cho người bị kick.
- **Thừa kế lãnh đạo**: Nếu Captain rời server hoặc hệ thống, bot sẽ tự động thực hiện quy trình thừa kế:
    - Ưu tiên Đội phó (Vice Captain) gia nhập sớm nhất được đôn lên làm Captain.
    - Nếu không có Đội phó, clan sẽ chuyển sang trạng thái **Không hoạt động (Inactive)** để chờ Mod can thiệp hoặc bổ nhiệm mới. Clan **không** tự động bị giải tán để bảo toàn lịch sử và thành viên.
- **Mời thành viên mới**: Captain hoặc Vice có thể mời người vào clan bằng lệnh `/clan invite @user`. Người được mời nhận lời mời qua DM.



Cho mượn thành viên giữa các clan
Clan muốn mượn người có thể gửi yêu cầu loan đến clan đang sở hữu thành viên đó.


Yêu cầu sẽ được gửi vào kênh chat riêng của clan cho mượn. Clan mượn tự động được tính là đồng ý khi gửi yêu cầu. Việc cho mượn cần sự đồng ý của 2 bên còn lại: Captain/Vice clan cho mượn (Accept trong kênh chat) và chính thành viên được mượn (Accept qua DM/Kênh chat). Khi thành công, thông báo sẽ được đăng tại `#chat-arena`.


Mỗi clan chỉ được có tối đa 2 người đang trong diện cho mượn (lending) hoặc đang mượn (borrowing) tại một thời điểm.


Thời hạn cho mượn mặc định tối đa 7 ngày (hoặc kết thúc sớm nếu captain hủy).


Cooldown sau khi kết thúc cho mượn là 14 ngày cho cả 2 clan và thành viên đó trước khi được thực hiện cho mượn/mượn tiếp.


Lách luật bằng cho mượn để boost hoặc gian lận Elo sẽ bị xử như gian lận.



Chuyển nhượng thành viên (Transfer)
Việc chuyển nhượng thành viên chính thức giữa các clan phải tuân thủ quy trình nghiêm ngặt.


Phải có 3 bên đồng ý: Captain/Vice clan nguồn (Source), Captain/Vice clan đích (Dest), và thành viên được chuyển nhượng.


Điều kiện:
Clan nguồn phải đảm bảo còn tối thiểu 5 thành viên sau khi chuyển đi. Nếu không đủ, lệnh chuyển nhượng sẽ bị từ chối.
Clan đích phải đang hoạt động (Active).


Hệ quả:
Thành viên sau khi chuyển sẽ bị "Transfer Sickness": Cấm thi đấu 3 ngày (72 giờ).
Thành viên chịu cooldown join/leave 14 ngày (không được rời clan mới trong 14 ngày).


Trận đấu custom và Elo
Các clan có thể tạo trận custom giữa nhau và ghi nhận kết quả bằng bot.


Trận đấu chỉ được ghi nhận và tính Elo khi:


cả hai clan đều đang hoạt động


trận được tạo bằng bot và hai bên đồng ý


kết quả được xác nhận bởi cả hai bên


Một bên báo cáo kết quả (kèm tỉ số), bên còn lại nhận thông báo vào kênh riêng để bấm xác nhận. Nếu phản đối hoặc không xác nhận, trận chuyển sang tranh chấp và chỉ mod được chốt.


Cả hai clan tham gia trận đều có thể báo cáo kết quả (không chỉ người tạo trận).


Hủy trận yêu cầu sự đồng thuận của cả hai bên: một bên yêu cầu hủy, bên kia phải xác nhận.


Elo khởi điểm của clan là 1000.


10 trận đầu là giai đoạn xếp hạng ban đầu: Elo thay đổi nhanh hơn (K=40).


Sau đó Elo thay đổi ổn định hơn (K=32).


Elo không thể xuống dưới 100 (để giữ tinh thần thi đấu).


Để chống farm Elo, giữa cùng 2 clan, Elo giảm dần sau mỗi trận trong 24 giờ (100% → 70% → 40% → 20%).



Thách đấu (Challenge)
Clan có thể thách đấu clan khác thông qua nút ⚔️ Thách đấu trên bảng #arena.


Khi gửi thách đấu, Captain/Vice chọn **thể thức** (BO1 / BO3 / BO5) và clan đối thủ.


Lời thách đấu được gửi vào kênh chat riêng của clan đối thủ, với nút Chấp nhận và Từ chối.


Chỉ Captain hoặc Vice Captain của clan đối thủ mới có quyền chấp nhận hoặc từ chối lời thách.


**Giới hạn**: Mỗi clan chỉ được tham gia tối đa **1 trận đấu chưa hoàn thành** tại một thời điểm. Phải hoàn thành trận hiện tại trước khi gửi hoặc nhận thách đấu mới.


Nếu chấp nhận, hai bên tiến hành **Ban/Pick Map** (Map Veto) ngay lập tức:
- **BO1**: Hai bên lần lượt ban map cho đến khi còn lại 1 map thi đấu.
- **BO3**: Ban 2 map mỗi bên → Pick 1 map mỗi bên → Ban 2 map mỗi bên → Map còn lại là Decider.
- **BO5**: Ban 2 map mỗi bên → Pick 2 map mỗi bên → Map còn lại là Decider.


Sau khi Map Veto hoàn tất, trận đấu được tạo tự động.


Nếu từ chối, clan thách đấu sẽ được thông báo.


Cooldown chống spam: 10 phút giữa các lần thách đấu từ cùng một clan.



Giải đấu (khi server tổ chức)
Khi server tổ chức giải, mod có thể bật chế độ giải và áp dụng luật giải riêng.


Trong chế độ giải, clan có thể bị yêu cầu khai roster chính và dùng đúng tài khoản chính để thi đấu.


Mod có thể khóa roster trong suốt giải.


Vi phạm luật giải sẽ bị xử theo hệ thống gian lận và case.



Gian lận, clone, boost và xử phạt
Các hành vi bị coi là gian lận gồm: dùng acc clone để lách luật, né cooldown, thao túng Elo; dùng người ngoài clan để boost; dàn xếp kết quả; spam trận để đẩy Elo; giả mạo danh tính.


Bot không thể tự chứng minh 100% “1 người ngoài đời dùng nhiều acc”, nên bot chỉ tự chặn các trường hợp chắc chắn và đánh dấu nghi vấn. Quyết định cuối cùng thuộc về mod.


Hình phạt có thể áp dụng
Cảnh cáo.


Hủy/rollback Elo các trận liên quan.


Reset Elo.


Cấm tham gia thi đấu/tính Elo theo thời hạn.


Kick thành viên liên quan.


Giải tán clan.
- **Xử lý khoản mượn**: Khi một clan bị giải tán, tất cả các thành viên đang trong diện cho mượn (loan) liên quan đến clan đó (bất kể là bên cho mượn hay bên mượn) sẽ được bot tự động chấm dứt khoản mượn ngay lập tức và đưa về trạng thái hợp lệ.


Cấm tham gia hệ thống clan.


Với vi phạm nghiêm trọng hoặc tái phạm (clone/boost có tổ chức), mod có quyền giải tán clan và cấm vĩnh viễn những tài khoản liên quan khỏi việc tham gia bất kỳ clan nào.



Report, tranh chấp và xử lý
Mọi người có thể dùng lệnh report để tố cáo clan/user/trận đấu có dấu hiệu gian lận.


Report phải có mô tả rõ ràng và bằng chứng nếu có.


Mỗi report tạo thành một “case” để mod xử lý.


Mod có thể yêu cầu thêm bằng chứng, tạm khóa clan khỏi việc tính Elo khi điều tra, và ra phán quyết.



Kháng cáo
Người bị phạt có quyền kháng cáo 1 lần trong vòng 7 ngày.


Kháng cáo phải nêu lý do và đưa bằng chứng mới nếu có.


Mod có quyền giữ nguyên án, giảm án, hoặc hủy án.



Mọi quyết định duyệt clan, xử phạt, rollback Elo, giải tán clan đều được bot ghi log để ban quản trị kiểm tra lại khi cần.

### Tự động dọn dẹp khi rời server
Hệ thống tự động xử lý khi một thành viên rời khỏi Discord server:
1. **Xóa dữ liệu**: Nếu người rời server không có lịch sử đấu (match history), họ sẽ bị xóa hoàn toàn khỏi database để bảo mật.
2. **Ẩn danh (Anonymize)**: Nếu người đó có lịch sử đấu (đã từng tạo hoặc tham gia trận), hệ thống sẽ không xóa mà thực hiện:
    - Đổi Riot ID thành `DeletedUser#ID`.
    - Đổi Discord ID thành `LEAVER_ID`.
    - Ban vĩnh viễn khỏi hệ thống clan.
    - Việc này giúp bảo toàn tính toàn vẹn của lịch sử đấu và Elo cho các clan khác.
3. **Dọn dẹp**: Tự động hủy các yêu cầu mượn/chuyển nhượng (loan/transfer) và bài đăng tìm clan của người đó.
