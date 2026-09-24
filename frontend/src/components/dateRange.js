export function toDateInput(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function lastDays(count, today = new Date()) {
  const from = new Date(today.getFullYear(), today.getMonth(), today.getDate() - (count - 1));
  return { from: toDateInput(from), to: toDateInput(today) };
}

export function eachDay(from, to) {
  const [fromYear, fromMonth, fromDay] = from.split("-").map(Number);
  const [toYear, toMonth, toDay] = to.split("-").map(Number);
  const cursor = new Date(fromYear, fromMonth - 1, fromDay);
  const end = new Date(toYear, toMonth - 1, toDay);
  const days = [];
  while (cursor <= end) {
    days.push(toDateInput(cursor));
    cursor.setDate(cursor.getDate() + 1);
  }
  return days;
}
