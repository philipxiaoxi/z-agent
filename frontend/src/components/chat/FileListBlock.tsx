import { memo } from "react";
import { Dropdown } from "antd";
import type { MenuProps } from "antd";
import {
  FolderOutlined,
  FileTextOutlined,
  FileImageOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  FileExcelOutlined,
  FilePptOutlined,
  FileZipOutlined,
  FileUnknownOutlined,
  DownOutlined,
  RightOutlined,
  InboxOutlined,
  SearchOutlined,
  EyeOutlined,
  PlusOutlined,
} from "@ant-design/icons";
import type { FileListData, FileItem } from "../../stores/chat-store";
import { useChatStore } from "../../stores/chat-store";

function formatSize(bytes: number): string {
  if (!bytes) return "";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return (bytes / Math.pow(1024, i)).toFixed(1) + " " + units[i];
}

function formatDate(ts: string): string {
  if (!ts) return "";
  const num = parseInt(ts, 10);
  const d = isNaN(num) ? new Date(ts) : new Date(num * 1000);
  if (isNaN(d.getTime())) return "";
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${month}/${day}`;
}

function getFileIcon(item: FileItem) {
  if (item.type === "folder") {
    return <FolderOutlined className="text-[28px]" style={{ color: "#faad14" }} />;
  }

  const ext = item.name.split(".").pop()?.toLowerCase() || "";

  const iconMap: Record<string, { icon: typeof FolderOutlined; color: string }> = {
    jpg: { icon: FileImageOutlined, color: "#52c41a" },
    jpeg: { icon: FileImageOutlined, color: "#52c41a" },
    png: { icon: FileImageOutlined, color: "#52c41a" },
    gif: { icon: FileImageOutlined, color: "#52c41a" },
    svg: { icon: FileImageOutlined, color: "#52c41a" },
    webp: { icon: FileImageOutlined, color: "#52c41a" },
    bmp: { icon: FileImageOutlined, color: "#52c41a" },
    pdf: { icon: FilePdfOutlined, color: "#ff4d4f" },
    doc: { icon: FileWordOutlined, color: "#1677ff" },
    docx: { icon: FileWordOutlined, color: "#1677ff" },
    xls: { icon: FileExcelOutlined, color: "#52c41a" },
    xlsx: { icon: FileExcelOutlined, color: "#52c41a" },
    ppt: { icon: FilePptOutlined, color: "#ff4d4f" },
    pptx: { icon: FilePptOutlined, color: "#ff4d4f" },
    zip: { icon: FileZipOutlined, color: "#faad14" },
    rar: { icon: FileZipOutlined, color: "#faad14" },
    "7z": { icon: FileZipOutlined, color: "#faad14" },
    tar: { icon: FileZipOutlined, color: "#faad14" },
    gz: { icon: FileZipOutlined, color: "#faad14" },
    mp3: { icon: FileUnknownOutlined, color: "#722ed1" },
    wav: { icon: FileUnknownOutlined, color: "#722ed1" },
    flac: { icon: FileUnknownOutlined, color: "#722ed1" },
    mp4: { icon: FileUnknownOutlined, color: "#eb2f96" },
    mov: { icon: FileUnknownOutlined, color: "#eb2f96" },
    avi: { icon: FileUnknownOutlined, color: "#eb2f96" },
    mkv: { icon: FileUnknownOutlined, color: "#eb2f96" },
  };

  const match = iconMap[ext];
  if (match) {
    const Icon = match.icon;
    return <Icon className="text-[28px]" style={{ color: match.color }} />;
  }

  return <FileTextOutlined className="text-[28px]" style={{ color: "#8c8c8c" }} />;
}

interface Props {
  fileList: FileListData;
  collapsed: boolean;
  blockId: string;
  onFileAction?: (action: "analyze" | "view" | "add_to_input", path: string) => void;
  onToggle?: () => void;
}

function normalizeItems(items: FileItem[]): FileItem[] {
  return items.map((item) => ({
    ...item,
    type: (["folder", "directory", "dir"].includes(item.type) ? "folder" : "file") as "file" | "folder",
    size: Number(item.size ?? 0),
  }));
}

export default memo(function FileListBlock({ fileList, collapsed, blockId, onFileAction, onToggle }: Props) {
  const storeToggle = useChatStore((s) => s.toggleBlockCollapsed);
  const toggle = onToggle ?? (() => storeToggle(blockId));
  const { path, current_path = path ?? "", items = [], total } = fileList;
  const normalizedItems = normalizeItems(items);

  const sorted = [...normalizedItems].sort((a, b) => {
    if (a.type !== b.type) return a.type === "folder" ? -1 : 1;
    return a.name.localeCompare(b.name, "zh-CN");
  });

  return (
    <div className="border border-gray-200 border-l-[3px] border-l-[#1677ff] rounded-lg bg-white text-[13px] overflow-hidden">
      <div
        onClick={() => toggle()}
        className="flex items-center gap-1.5 px-3.5 py-2.5 cursor-pointer select-none bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        {collapsed ? (
          <RightOutlined style={{ color: "#1677ff", fontSize: 12 }} />
        ) : (
          <DownOutlined style={{ color: "#1677ff", fontSize: 12 }} />
        )}
        <FolderOutlined className="text-sm" style={{ color: "#1677ff" }} />
        <span className="font-semibold text-gray-700 truncate flex-1 ml-0.5">
          {current_path || "文件列表"}
        </span>
        <span className="text-xs text-gray-400 whitespace-nowrap">共 {total || normalizedItems.length} 项</span>
      </div>

      {!collapsed && (
        <div className="p-3">
          {normalizedItems.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-8 text-gray-400">
              <InboxOutlined className="text-4xl opacity-30" />
              <span className="text-sm">此目录为空</span>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
              {sorted.map((item) => {
                const sep = current_path.endsWith("/") ? "" : "/";
                const fullPath = current_path + sep + item.name;

                const menuItems: MenuProps["items"] = [
                  { key: "analyze", icon: <SearchOutlined />, label: "分析文件" },
                  { key: "view", icon: <EyeOutlined />, label: "查看文件" },
                  { key: "add_to_input", icon: <PlusOutlined />, label: "添加到输入框" },
                ];

                return (
                  <Dropdown
                    key={item.name}
                    menu={{
                      items: menuItems,
                      onClick: ({ key }) =>
                        onFileAction?.(key as "analyze" | "view" | "add_to_input", fullPath),
                    }}
                    trigger={["click"]}
                  >
                    <div className="flex flex-col items-center gap-1.5 p-3 rounded-lg border border-transparent transition-colors cursor-pointer hover:border-gray-200 hover:bg-gray-50">
                      {getFileIcon(item)}
                      <span
                        className="text-xs text-gray-700 text-center leading-tight truncate w-full"
                        title={item.name}
                      >
                        {item.name}
                      </span>
                      <span className="text-[11px] text-gray-400 leading-none">
                        {item.type === "folder"
                          ? formatDate(item.modified_at || "")
                          : formatSize(item.size || 0)}
                      </span>
                    </div>
                  </Dropdown>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
});
