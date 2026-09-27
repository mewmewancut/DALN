import { useEffect, useMemo, useRef, useState } from "react";

export function normalizeSearch(value) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase();
}

export default function SearchableSelect({ label, options, value, onChange, disabled = false }) {
  const selected = options.find((option) => option.code === value);
  const selectedName = selected?.name;
  const [query, setQuery] = useState(selected?.name ?? "");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const inputRef = useRef(null);
  const typingRef = useRef(false);

  useEffect(() => {
    if (selectedName) {
      setQuery(selectedName);
    } else if (typingRef.current) {
      typingRef.current = false;
    } else {
      setQuery("");
    }
  }, [selectedName, value]);

  useEffect(() => {
    inputRef.current?.setCustomValidity(
      value || disabled ? "" : `Vui lòng chọn ${label.toLowerCase()} từ danh sách`,
    );
  }, [disabled, label, value]);

  const filtered = useMemo(() => {
    const term = normalizeSearch(query.trim());
    if (!term || selectedName === query) return options;
    return options.filter((option) => normalizeSearch(option.name).includes(term));
  }, [options, query, selectedName]);

  function choose(option) {
    setQuery(option.name);
    onChange(option.code);
    setOpen(false);
  }

  function keyDown(event) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      const direction = event.key === "ArrowDown" ? 1 : -1;
      setActiveIndex((current) => Math.max(0, Math.min(filtered.length - 1, current + direction)));
    } else if (event.key === "Enter" && open && filtered[activeIndex]) {
      event.preventDefault();
      choose(filtered[activeIndex]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <label className="searchable-select">
      {label}
      <input
        ref={inputRef}
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        required
        value={query}
        disabled={disabled}
        placeholder={disabled ? "Chọn Tỉnh/Thành phố trước" : `Tìm ${label.toLowerCase()}`}
        onFocus={() => setOpen(true)}
        onBlur={() => {
          setOpen(false);
          if (query !== (selectedName ?? "")) {
            setQuery("");
            onChange("");
          }
        }}
        onKeyDown={keyDown}
        onChange={(event) => {
          typingRef.current = true;
          setQuery(event.target.value);
          onChange("");
          setActiveIndex(-1);
          setOpen(true);
        }}
      />
      {open && !disabled && (
        <ul role="listbox" className="searchable-options">
          {filtered.slice(0, 60).map((option, index) => (
            <li
              role="option"
              aria-selected={option.code === value}
              className={index === activeIndex ? "is-active" : ""}
              key={option.code}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => choose(option)}
            >
              {option.name}
            </li>
          ))}
          {filtered.length === 0 && <li className="empty-option">Không tìm thấy kết quả</li>}
        </ul>
      )}
    </label>
  );
}
