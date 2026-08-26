const form = document.querySelector<HTMLFormElement>("#chart-form");
const birthDate = document.querySelector<HTMLInputElement>('[name="birth_date"]');
const solarYear = document.querySelector<HTMLInputElement>('[name="solar_year"]');
const solarMonth = document.querySelector<HTMLInputElement>('[name="solar_month"]');
const solarDay = document.querySelector<HTMLInputElement>('[name="solar_day"]');

function pad(value: number, width: number): string {
  return String(value).padStart(width, "0");
}

export function composeSolarDate(yearText: string, monthText: string, dayText: string): string {
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  if (
    !Number.isInteger(year) ||
    !Number.isInteger(month) ||
    !Number.isInteger(day) ||
    year < 1901 ||
    year > 2099 ||
    month < 1 ||
    month > 12 ||
    day < 1 ||
    day > 31
  ) {
    return "";
  }

  const candidate = new Date(Date.UTC(year, month - 1, day));
  if (
    candidate.getUTCFullYear() !== year ||
    candidate.getUTCMonth() !== month - 1 ||
    candidate.getUTCDate() !== day
  ) {
    return "";
  }
  return `${pad(year, 4)}-${pad(month, 2)}-${pad(day, 2)}`;
}

function syncPartsFromBirthDate(): void {
  if (!birthDate || !solarYear || !solarMonth || !solarDay) return;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(birthDate.value);
  if (!match) {
    solarYear.value = "";
    solarMonth.value = "";
    solarDay.value = "";
    return;
  }
  solarYear.value = String(Number(match[1]));
  solarMonth.value = String(Number(match[2]));
  solarDay.value = String(Number(match[3]));
}

function syncBirthDateFromParts(): void {
  if (!birthDate || !solarYear || !solarMonth || !solarDay) return;
  const value = composeSolarDate(solarYear.value, solarMonth.value, solarDay.value);
  if (birthDate.value === value) return;
  birthDate.value = value;
  birthDate.dispatchEvent(new Event("input", { bubbles: true }));
}

function updateSolarPartState(clearInactive = false): void {
  if (!form || !solarYear || !solarMonth || !solarDay) return;
  const calendar = new FormData(form).get("calendar")?.toString() ?? "solar";
  const active = calendar === "solar";
  for (const input of [solarYear, solarMonth, solarDay]) {
    input.disabled = !active;
  }
  if (!active && clearInactive) {
    solarYear.value = "";
    solarMonth.value = "";
    solarDay.value = "";
  }
}

if (form && birthDate && solarYear && solarMonth && solarDay) {
  for (const input of [solarYear, solarMonth, solarDay]) {
    input.addEventListener("input", syncBirthDateFromParts);
    input.addEventListener("change", syncBirthDateFromParts);
  }

  birthDate.addEventListener("input", syncPartsFromBirthDate);
  birthDate.addEventListener("change", syncPartsFromBirthDate);

  form.addEventListener("change", (event) => {
    const target = event.target;
    if (target instanceof HTMLInputElement && target.name === "calendar") {
      updateSolarPartState(true);
    }
  });

  form.addEventListener("reset", () => {
    queueMicrotask(() => {
      updateSolarPartState();
      syncPartsFromBirthDate();
    });
  });

  updateSolarPartState();
  syncPartsFromBirthDate();
}
