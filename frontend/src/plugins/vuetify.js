import 'vuetify/styles';
import { createVuetify } from 'vuetify';
import { h } from 'vue';
import { paperMindDark, paperMindLight } from '../theme/tokens';
import * as REGISTERED_ICONS from './mdiIcons.js';
import { aliases as mdiAliases } from 'vuetify/iconsets/mdi-svg';
import { VSvgIcon } from 'vuetify/lib/composables/icons';

/**
 * Wandelt einen @mdi/js-Bezeichner in den in Templates genutzten kebab-Namen um:
 *   mdiAccountCircleOutline -> mdi-account-circle-outline
 *   mdiCpu64Bit             -> mdi-cpu-64-bit
 */
function camelToKebab(name) {
  return name
    .replace(/([a-z])([A-Z])/g, '$1-$2')
    .replace(/([A-Za-z])([0-9])/g, '$1-$2')
    .replace(/([0-9])([A-Z])/g, '$1-$2')
    .toLowerCase();
}

/**
 * Bewusste Aliase: Template-Name -> abweichendes Glyph. Nur hier eintragen,
 * wenn ein kebab-Name absichtlich auf ein ANDERES Icon zeigen soll als die
 * automatische Ableitung ergaebe.
 */
const ICON_OVERRIDES = {
  // Gefuellte statt Outline-Variante (historisches Verhalten beibehalten).
  'mdi-delete-forever-outline': REGISTERED_ICONS.mdiDeleteForever,
};

// Vollautomatisch aus mdiIcons.js erzeugt - kein manuelles Mapping noetig.
const mdiPathMap = {};
for (const [name, path] of Object.entries(REGISTERED_ICONS)) {
  mdiPathMap[camelToKebab(name)] = path;
}
Object.assign(mdiPathMap, ICON_OVERRIDES);

function resolveMdiPath(iconName) {
  if (!iconName) {
    return REGISTERED_ICONS.mdiInformationOutline;
  }
  if (iconName.startsWith('svg:')) {
    return iconName.slice(4);
  }
  return mdiPathMap[iconName] || REGISTERED_ICONS.mdiInformationOutline;
}

const mdi = {
  component: (props) => {
    const iconPath = resolveMdiPath(props.icon);
    return h(VSvgIcon, { ...props, icon: iconPath });
  }
};

const vuetify = createVuetify({
  theme: {
    defaultTheme: 'light',
    themes: {
      light: {
        dark: false,
        colors: {
          background: paperMindLight.background,
          surface: paperMindLight.surface,
          primary: paperMindLight.primary,
          'on-background': paperMindLight.text,
          'on-surface': paperMindLight.text,
          'surface-2': paperMindLight.surface2,
          'surface-3': paperMindLight.surface3,
          'surface-hover': paperMindLight.surfaceHover,
          'panel-left': paperMindLight.sidebar,
          'panel-mid': paperMindLight.panelMid,
          'panel-right': paperMindLight.panelRight,
          'card': paperMindLight.card,
          'card-hover': paperMindLight.cardHover,
          'card-active': paperMindLight.cardActive,
          'text-muted': paperMindLight.textMuted,
          divider: paperMindLight.divider,
          outline: paperMindLight.outline,
          'divider-soft': paperMindLight.dividerSoft
        }
      },
      dark: {
        dark: true,
        colors: {
          background: paperMindDark.background,
          surface: paperMindDark.surface,
          primary: paperMindDark.primary,
          'on-background': paperMindDark.text,
          'on-surface': paperMindDark.text,
          'surface-2': paperMindDark.surface2,
          'surface-3': paperMindDark.surface3,
          'surface-hover': paperMindDark.surfaceHover,
          'panel-left': paperMindDark.sidebar,
          'panel-mid': paperMindDark.panelMid,
          'panel-right': paperMindDark.panelRight,
          'card': paperMindDark.card,
          'card-hover': paperMindDark.cardHover,
          'card-active': paperMindDark.cardActive,
          'text-muted': paperMindDark.textMuted,
          divider: paperMindDark.divider,
          outline: paperMindDark.outline,
          'divider-soft': paperMindDark.dividerSoft
        }
      }
    }
  },
  icons: {
    defaultSet: 'mdi',
    aliases: mdiAliases,
    sets: {
      mdi
    }
  }
});

export default vuetify;
