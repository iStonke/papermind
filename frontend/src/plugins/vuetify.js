import 'vuetify/styles';
import { createVuetify } from 'vuetify';
import { h } from 'vue';
import { paperMindDark, paperMindLight } from '../theme/tokens';
import {
  mdiAlertCircleOutline,
  mdiCheckboxMultipleOutline,
  mdiBookOpenPageVariantOutline,
  mdiCamera,
  mdiCameraOffOutline,
  mdiCallSplit,
  mdiChevronDown,
  mdiChevronUp,
  mdiCheck,
  mdiCheckCircleOutline,
  mdiClose,
  mdiCogOutline,
  mdiContentCopy,
  mdiCreation,
  mdiDotsHorizontal,
  mdiDotsVertical,
  mdiDownloadOutline,
  mdiDeleteOutline,
  mdiFileDocumentMultipleOutline,
  mdiFileDocumentOutline,
  mdiFileAlertOutline,
  mdiFileImageOutline,
  mdiFilePdfBox,
  mdiFileUploadOutline,
  mdiFilterVariant,
  mdiFolder,
  mdiFolderPlusOutline,
  mdiFolderOutline,
  mdiFolderSearchOutline,
  mdiInboxArrowDownOutline,
  mdiInformationOutline,
  mdiKeyboardOutline,
  mdiMagnify,
  mdiPencilOutline,
  mdiPlus,
  mdiProgressClock,
  mdiRefresh,
  mdiRotateLeft,
  mdiRotateRight,
  mdiRobot,
  mdiRobotOutline,
  mdiSendOutline,
  mdiSort,
  mdiSourceMerge,
  mdiStar,
  mdiStarOutline,
  mdiRestore,
  mdiDeleteForever,
  mdiTagOffOutline,
  mdiTagMultipleOutline,
  mdiTagOutline,
  mdiTagTextOutline,
  mdiTextRecognition,
  mdiTrashCanOutline,
  mdiTrayArrowDown,
  mdiTrayArrowUp
} from '@mdi/js';
import { aliases as mdiAliases } from 'vuetify/iconsets/mdi-svg';
import { VSvgIcon } from 'vuetify/lib/composables/icons';

const mdiPathMap = {
  'mdi-alert-circle-outline': mdiAlertCircleOutline,
  'mdi-book-open-page-variant-outline': mdiBookOpenPageVariantOutline,
  'mdi-camera': mdiCamera,
  'mdi-camera-off-outline': mdiCameraOffOutline,
  'mdi-call-split': mdiCallSplit,
  'mdi-chevron-down': mdiChevronDown,
  'mdi-chevron-up': mdiChevronUp,
  'mdi-check': mdiCheck,
  'mdi-checkbox-multiple-outline': mdiCheckboxMultipleOutline,
  'mdi-check-circle-outline': mdiCheckCircleOutline,
  'mdi-close': mdiClose,
  'mdi-cog-outline': mdiCogOutline,
  'mdi-content-copy': mdiContentCopy,
  'mdi-creation': mdiCreation,
  'mdi-dots-horizontal': mdiDotsHorizontal,
  'mdi-dots-vertical': mdiDotsVertical,
  'mdi-download-outline': mdiDownloadOutline,
  'mdi-delete-outline': mdiDeleteOutline,
  'mdi-file-document-multiple-outline': mdiFileDocumentMultipleOutline,
  'mdi-file-document-outline': mdiFileDocumentOutline,
  'mdi-file-alert-outline': mdiFileAlertOutline,
  'mdi-file-image-outline': mdiFileImageOutline,
  'mdi-file-pdf-box': mdiFilePdfBox,
  'mdi-file-upload-outline': mdiFileUploadOutline,
  'mdi-filter-variant': mdiFilterVariant,
  'mdi-folder': mdiFolder,
  'mdi-folder-plus-outline': mdiFolderPlusOutline,
  'mdi-folder-outline': mdiFolderOutline,
  'mdi-folder-search-outline': mdiFolderSearchOutline,
  'mdi-inbox-arrow-down-outline': mdiInboxArrowDownOutline,
  'mdi-information-outline': mdiInformationOutline,
  'mdi-keyboard-outline': mdiKeyboardOutline,
  'mdi-magnify': mdiMagnify,
  'mdi-pencil-outline': mdiPencilOutline,
  'mdi-plus': mdiPlus,
  'mdi-progress-clock': mdiProgressClock,
  'mdi-refresh': mdiRefresh,
  'mdi-rotate-left': mdiRotateLeft,
  'mdi-rotate-right': mdiRotateRight,
  'mdi-robot': mdiRobot,
  'mdi-robot-outline': mdiRobotOutline,
  'mdi-send-outline': mdiSendOutline,
  'mdi-sort': mdiSort,
  'mdi-source-merge': mdiSourceMerge,
  'mdi-star': mdiStar,
  'mdi-star-outline': mdiStarOutline,
  'mdi-restore': mdiRestore,
  'mdi-delete-forever-outline': mdiDeleteForever,
  'mdi-tag-off-outline': mdiTagOffOutline,
  'mdi-tag-multiple-outline': mdiTagMultipleOutline,
  'mdi-tag-outline': mdiTagOutline,
  'mdi-tag-text-outline': mdiTagTextOutline,
  'mdi-text-recognition': mdiTextRecognition,
  'mdi-trash-can-outline': mdiTrashCanOutline,
  'mdi-tray-arrow-down': mdiTrayArrowDown,
  'mdi-tray-arrow-up': mdiTrayArrowUp
};

function resolveMdiPath(iconName) {
  if (!iconName) {
    return mdiInformationOutline;
  }
  if (iconName.startsWith('svg:')) {
    return iconName.slice(4);
  }

  const path = mdiPathMap[iconName];
  if (path) {
    return path;
  }

  return mdiInformationOutline;
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
