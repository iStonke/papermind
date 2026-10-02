const measured = new WeakMap();
export function resizeThoughtText(input) {
  if (!input) return;
  const width = input.clientWidth;
  const previous = measured.get(input);
  if (previous?.text === input.value && previous.width === width) return;
  input.style.height = '0px';
  input.style.height = `${input.scrollHeight}px`;
  measured.set(input, { text:input.value, width });
}
