// Include radio/checkbox menu items: layout choices use menuitemradio.
export function menuItemsOf(dropdown) {
  return dropdown
    ? Array.from(dropdown.querySelectorAll('[role="menuitem"], [role="menuitemradio"], [role="menuitemcheckbox"]'))
      .filter((item) => !item.disabled && item.getAttribute('aria-disabled') !== 'true')
    : [];
}

export function nextMenuItem(items, current, key) {
  if (!items.length) return null;
  const index = items.indexOf(current);
  if (key === 'Home') return items[0];
  if (key === 'End') return items.at(-1);
  if (key === 'ArrowDown') return items[index < 0 ? 0 : (index + 1) % items.length];
  if (key === 'ArrowUp') return items[index < 0 ? items.length - 1 : (index - 1 + items.length) % items.length];
  return null;
}
