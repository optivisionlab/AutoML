/**
 * Ép kiểu giá trị người dùng nhập ở form dự đoán theo kiểu THẬT của cột lúc train.
 *
 * Endpoint deployment ghi mọi feature là "float", nên không dựa vào đó được.
 * Kiểu thật lấy từ preview của dataset (GET /datasets/{id}/data): cột chữ như
 * "001" / "A01" phải gửi nguyên chữ - đổi "001" thành số 1 là model nhận một
 * giá trị khác hẳn lúc train (mất số 0 đầu, thành nhóm lạ).
 */

export type FeatureKind = "number" | "string" | "boolean";

/** Kiểu của từng feature theo các dòng preview. Cột không có giá trị nào thì không biết (undefined). */
export function featureKinds(
  rows: Record<string, unknown>[] | undefined,
  features: string[],
): Record<string, FeatureKind | undefined> {
  const kinds: Record<string, FeatureKind | undefined> = {};
  for (const name of features) {
    const values = (rows ?? []).map((row) => row?.[name]).filter((value) => value !== null && value !== undefined);
    if (!values.length) continue;
    kinds[name] = values.every((value) => typeof value === "number")
      ? "number"
      : values.every((value) => typeof value === "boolean")
        ? "boolean"
        : "string";
  }
  return kinds;
}

/**
 * Giá trị gửi đi cho một feature.
 *
 * - time_series: luôn gửi chữ. Cột thời gian kiểu "20250101" mà thành số thì
 *   pandas đọc là epoch nano giây; cột số khác model time_series tự ép kiểu.
 * - Cột chữ (theo preview): gửi nguyên chữ.
 * - Cột số, hoặc chưa biết kiểu: chữ số thì gửi dạng số như trước.
 */
export function coerceFeature(value: string, kind: FeatureKind | undefined, timeSeries: boolean): string | number | boolean {
  const trimmed = value.trim();
  if (timeSeries || kind === "string") return trimmed;
  // Cột boolean lúc train: gửi JSON true/false - chuỗi "true" không đổi được thành số ở backend.
  if (kind === "boolean") return BOOLEAN_TEXT[trimmed.toLowerCase()] ?? trimmed;
  // Chỉ số thập phân bình thường. Number() còn nhận "0x1A" (=26), "Infinity", và
  // "1e400" thành Infinity - JSON gửi đi thành null. Số nguyên quá 2^53 mất chính xác
  // (vd mã dài) - gửi nguyên chữ thì backend còn tự xử lý được.
  if (!DECIMAL.test(trimmed)) return trimmed;
  const number = Number(trimmed);
  if (!Number.isFinite(number) || (Number.isInteger(number) && !Number.isSafeInteger(number))) return trimmed;
  return number;
}

const BOOLEAN_TEXT: Record<string, boolean> = {
  true: true, false: false, "1": true, "0": false, yes: true, no: false,
  "có": true, "không": false, "đúng": true, "sai": false,
};

const DECIMAL = /^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/;

// ------------------------------------------------------------- time_series

const DAY_MS = 24 * 60 * 60 * 1000;
// Mốc ISO không múi giờ, như preview của backend trả về ("2014-04-01T00:00:00") hoặc người dùng gõ.
const TIMESTAMP = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?)?$/;

/**
 * Mốc thời gian -> ms, tính như UTC để cộng bước không bị lệch vì giờ mùa hè.
 * Giữ phần lẻ tới mili giây; lẻ hơn thế (micro/nano giây khác 0) thì không biểu
 * diễn đúng được - trả null như khi không phải mốc thời gian.
 */
export function parseTimestamp(value: unknown): number | null {
  if (typeof value !== "string") return null;
  const match = TIMESTAMP.exec(value.trim());
  if (!match) return null;
  const [, y, mo, d, h = "0", mi = "0", s = "0", fraction = ""] = match;
  if (/[1-9]/.test(fraction.slice(3))) return null;
  const millis = Number(fraction.slice(0, 3).padEnd(3, "0"));
  const ms = Date.UTC(Number(y), Number(mo) - 1, Number(d), Number(h), Number(mi), Number(s), millis);
  return Number.isFinite(ms) ? ms : null;
}

function formatTimestamp(ms: number, style: "date" | "seconds" | "millis"): string {
  const iso = new Date(ms).toISOString();
  if (style === "date") return iso.slice(0, 10);
  return `${iso.slice(0, 10)} ${iso.slice(11, style === "millis" ? 23 : 19)}`;
}

export interface SeriesHint {
  /** Cột thời gian trong list_feature. */
  column: string;
  /** Mốc cuối của dữ liệu huấn luyện. */
  last: string;
  /** Mốc hợp lệ đầu tiên để dự báo. */
  next: string;
  stepMs: number;
  /**
   * true = ước tính từ một phần dữ liệu, đúng khi file xếp theo thời gian.
   * false = tính trên TOÀN BỘ dataset đúng như backend.
   */
  estimated: boolean;
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

/**
 * Mốc cuối lúc train và mốc kế tiếp để dự báo.
 *
 * Model time_series được dựng từ TOÀN BỘ dataset (TimeSeriesForecaster):
 * last_time = mốc lớn nhất, interval = trung vị khoảng cách giữa các mốc đã sắp
 * xếp. `rows` chứa đủ cả dataset (rows.length >= totalRows) thì tính đúng y như
 * vậy. Chỉ có một phần (preview 50 dòng đầu) thì chỉ ƯỚC TÍNH, giả định file xếp
 * theo thời gian: backend tự sắp xếp nên một phần đầu đều đặn chưa chứng minh được
 * cả file đã xếp - kết quả đánh dấu estimated để giao diện nói rõ.
 */
export function timeSeriesHint(
  rows: Record<string, unknown>[] | undefined,
  features: string[],
  totalRows: number | undefined,
): SeriesHint | null {
  if (!rows?.length || typeof totalRows !== "number" || totalRows < 2) return null;
  for (const column of features) {
    const parsed = rows.map((row) => row?.[column]).filter((v) => v !== null && v !== undefined).map(parseTimestamp);
    if (parsed.length < 2 || parsed.some((t) => t === null)) continue;
    const times = parsed as number[];

    let last: number;
    let stepMs: number;
    const estimated = times.length < totalRows;
    if (!estimated) {
      const sorted = [...times].sort((a, b) => a - b);
      stepMs = median(sorted.slice(1).map((t, i) => t - sorted[i]));
      last = sorted[sorted.length - 1];
    } else {
      const step = times[1] - times[0];
      if (step === 0 || times.some((t, i) => i > 0 && t - times[i - 1] !== step)) return null;
      stepMs = Math.abs(step);
      last = step > 0 ? times[0] + step * (totalRows - 1) : times[0];
    }
    if (!(stepMs > 0) || !Number.isFinite(last + stepMs) || Math.abs(last + stepMs) > 8.64e15) return null;

    const all = [...times, last + stepMs];
    const style = all.some((t) => t % 1000 !== 0)
      ? "millis"
      : stepMs % DAY_MS === 0 && all.every((t) => t % DAY_MS === 0)
        ? "date"
        : "seconds";
    return { column, last: formatTimestamp(last, style), next: formatTimestamp(last + stepMs, style), stepMs, estimated };
  }
  return null;
}

/** Bước thời gian -> đơn vị lớn nhất chia hết, để hiện cho người dùng. */
export function stepUnit(stepMs: number): { unit: "days" | "hours" | "minutes" | "seconds"; n: number } {
  if (stepMs % DAY_MS === 0) return { unit: "days", n: stepMs / DAY_MS };
  if (stepMs % 3_600_000 === 0) return { unit: "hours", n: stepMs / 3_600_000 };
  if (stepMs % 60_000 === 0) return { unit: "minutes", n: stepMs / 60_000 };
  return { unit: "seconds", n: stepMs / 1000 };
}

/**
 * Lỗi dự đoán của backend kèm nguyên traceback của worker
 * ("... Traceback (most recent call last): File ... ValueError: <câu lỗi>"): chỉ giữ câu lỗi cuối.
 */
export function shortBackendError(text: string): string {
  if (!text.includes("Traceback")) return text;
  const pattern = /\b[A-Z][A-Za-z]*(?:Error|Exception): /g;
  let last: RegExpExecArray | null = null;
  for (let match = pattern.exec(text); match; match = pattern.exec(text)) last = match;
  return last ? text.slice(last.index + last[0].length).trim() : text;
}
