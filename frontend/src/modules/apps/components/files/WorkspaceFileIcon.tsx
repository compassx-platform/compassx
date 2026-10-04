import type { LucideIcon } from 'lucide-react';
import {
  Database as DatabaseIcon,
  FileArchive as FileArchiveIcon,
  FileAudio as FileAudioIcon,
  FileCode2 as FileCode2Icon,
  File as FileIcon,
  FileImage as FileImageIcon,
  FileJson as FileJsonIcon,
  FileSpreadsheet as FileSpreadsheetIcon,
  FileText as FileTextIcon,
  FileType as FileTypeIcon,
  FileVideo as FileVideoIcon,
  Presentation as PresentationIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';

export type FileTypeGroup =
  | 'pdf'
  | 'document'
  | 'spreadsheet'
  | 'presentation'
  | 'archive'
  | 'json'
  | 'code'
  | 'image'
  | 'video'
  | 'audio'
  | 'database'
  | 'font'
  | 'generic';

export type TagColor =
  | 'coral'
  | 'blue'
  | 'lime'
  | 'lemon'
  | 'brown'
  | 'purple'
  | 'pink'
  | 'indigo'
  | 'default';

export interface FileVisual {
  group: FileTypeGroup;
  tagColor: TagColor;
  Icon: LucideIcon;
  colorClass: string;
}

const DOCUMENT_EXTENSIONS = new Set(['doc', 'docx', 'txt', 'md', 'rtf', 'log']);
const SPREADSHEET_EXTENSIONS = new Set(['xls', 'xlsx', 'csv', 'tsv']);
const PRESENTATION_EXTENSIONS = new Set(['ppt', 'pptx', 'key']);
const ARCHIVE_EXTENSIONS = new Set(['zip', 'rar', '7z', 'tar', 'gz', 'bz2']);
const JSON_EXTENSIONS = new Set(['json', 'jsonl', 'geojson']);
const CODE_EXTENSIONS = new Set([
  'js',
  'jsx',
  'ts',
  'tsx',
  'py',
  'rb',
  'go',
  'rs',
  'java',
  'c',
  'cpp',
  'h',
  'hpp',
  'html',
  'css',
  'scss',
  'sass',
  'less',
  'xml',
  'yaml',
  'yml',
  'toml',
  'sh',
  'bash',
  'zsh',
  'bat',
  'ps1',
]);
const IMAGE_EXTENSIONS = new Set([
  'avif',
  'bmp',
  'gif',
  'heic',
  'heif',
  'ico',
  'jpeg',
  'jpg',
  'png',
  'svg',
  'tif',
  'tiff',
  'webp',
]);
const VIDEO_EXTENSIONS = new Set([
  'avi',
  'flv',
  'm4v',
  'mkv',
  'mov',
  'mp4',
  'mpeg',
  'mpg',
  'webm',
  'wmv',
]);
const AUDIO_EXTENSIONS = new Set(['aac', 'flac', 'm4a', 'mp3', 'ogg', 'opus', 'wav', 'wma']);
const DATABASE_EXTENSIONS = new Set(['sql', 'db', 'sqlite', 'sqlite3']);
const FONT_EXTENSIONS = new Set(['ttf', 'otf', 'woff', 'woff2']);

const VISUALS: Record<FileTypeGroup, FileVisual> = {
  pdf: {
    group: 'pdf',
    tagColor: 'coral',
    Icon: FileTextIcon,
    colorClass: 'text-orange-500',
  },
  document: {
    group: 'document',
    tagColor: 'blue',
    Icon: FileTextIcon,
    colorClass: 'text-blue-400',
  },
  spreadsheet: {
    group: 'spreadsheet',
    tagColor: 'lime',
    Icon: FileSpreadsheetIcon,
    colorClass: 'text-emerald-400',
  },
  presentation: {
    group: 'presentation',
    tagColor: 'lemon',
    Icon: PresentationIcon,
    colorClass: 'text-amber-400',
  },
  archive: {
    group: 'archive',
    tagColor: 'brown',
    Icon: FileArchiveIcon,
    colorClass: 'text-amber-500',
  },
  json: {
    group: 'json',
    tagColor: 'purple',
    Icon: FileJsonIcon,
    colorClass: 'text-amber-400',
  },
  code: {
    group: 'code',
    tagColor: 'purple',
    Icon: FileCode2Icon,
    colorClass: 'text-sky-400',
  },
  image: {
    group: 'image',
    tagColor: 'pink',
    Icon: FileImageIcon,
    colorClass: 'text-pink-400',
  },
  video: {
    group: 'video',
    tagColor: 'indigo',
    Icon: FileVideoIcon,
    colorClass: 'text-indigo-400',
  },
  audio: {
    group: 'audio',
    tagColor: 'indigo',
    Icon: FileAudioIcon,
    colorClass: 'text-indigo-400',
  },
  database: {
    group: 'database',
    tagColor: 'purple',
    Icon: DatabaseIcon,
    colorClass: 'text-purple-400',
  },
  font: {
    group: 'font',
    tagColor: 'default',
    Icon: FileTypeIcon,
    colorClass: 'text-slate-400',
  },
  generic: {
    group: 'generic',
    tagColor: 'default',
    Icon: FileIcon,
    colorClass: 'text-slate-400',
  },
};

function extensionOf(path: string): string {
  const parts = path.split('/');
  const name = parts[parts.length - 1] ?? path;
  const dot = name.lastIndexOf('.');
  return dot > 0 ? name.slice(dot + 1).toLowerCase() : '';
}

export function workspaceFileVisual(path: string, mimeType?: string | null): FileVisual {
  const mime = mimeType?.split(';')[0]?.trim().toLowerCase() ?? '';
  if (mime === 'application/pdf') return VISUALS.pdf;
  if (mime.startsWith('image/')) return VISUALS.image;
  if (mime.startsWith('video/')) return VISUALS.video;
  if (mime.startsWith('audio/')) return VISUALS.audio;
  if (mime === 'application/json' || mime.endsWith('+json')) return VISUALS.json;

  const extension = extensionOf(path);
  if (extension === 'pdf') return VISUALS.pdf;
  if (DOCUMENT_EXTENSIONS.has(extension)) return VISUALS.document;
  if (SPREADSHEET_EXTENSIONS.has(extension)) return VISUALS.spreadsheet;
  if (PRESENTATION_EXTENSIONS.has(extension)) return VISUALS.presentation;
  if (ARCHIVE_EXTENSIONS.has(extension)) return VISUALS.archive;
  if (JSON_EXTENSIONS.has(extension)) return VISUALS.json;
  if (CODE_EXTENSIONS.has(extension)) return VISUALS.code;
  if (IMAGE_EXTENSIONS.has(extension)) return VISUALS.image;
  if (VIDEO_EXTENSIONS.has(extension)) return VISUALS.video;
  if (AUDIO_EXTENSIONS.has(extension)) return VISUALS.audio;
  if (DATABASE_EXTENSIONS.has(extension)) return VISUALS.database;
  if (FONT_EXTENSIONS.has(extension)) return VISUALS.font;
  return VISUALS.generic;
}

export function WorkspaceFileIcon({
  path,
  mimeType,
  className,
}: {
  path: string;
  mimeType?: string | null;
  className?: string;
}) {
  const visual = workspaceFileVisual(path, mimeType);
  return (
    <visual.Icon
      aria-hidden
      data-file-type={visual.group}
      data-tag-color={visual.tagColor}
      className={cn('size-3.5 shrink-0', visual.colorClass, className)}
    />
  );
}
