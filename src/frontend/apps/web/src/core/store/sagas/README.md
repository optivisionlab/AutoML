# Redux Saga boundary

Chỉ thêm `redux-saga` và saga thật khi workflow đủ phức tạp để cần `race`,
`cancel`, retry/backoff nhiều bước, hoặc phối hợp nhiều endpoint trong thời gian
dài.

Các luồng hiện tại nên ưu tiên:

- RTK Query cho server state và cache.
- Redux Listener Middleware cho side effect nhẹ sau action.
- Slice thường cho UI/client state.

Ứng viên saga sau này: training job lifecycle, batch inference có cancel,
hoặc orchestration nhiều worker/job kéo dài.
