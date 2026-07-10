import { memo, useEffect } from "react";
import { DownOutlined, RightOutlined, CodeOutlined } from "@ant-design/icons";
import type { HtmlPreviewData } from "../../stores/chat-store";
import { useChatStore } from "../../stores/chat-store";

const API_SCRIPT = `<script>
window.__zspace = {
  fillInput: function(text) {
    window.parent.postMessage({source:'zspace-html-preview',action:'fillInput',text:String(text)},'*');
  }
};
<\/script>`;

function injectApi(html: string): string {
  if (html.includes("</head>")) {
    return html.replace("</head>", API_SCRIPT + "</head>");
  }
  if (html.includes("</body>")) {
    return html.replace("</body>", API_SCRIPT + "</body>");
  }
  return API_SCRIPT + html;
}

interface Props {
  htmlPreview: HtmlPreviewData;
  collapsed: boolean;
  blockId: string;
}

export default memo(function HtmlPreviewBlock({ htmlPreview, collapsed, blockId }: Props) {
  const toggle = useChatStore((s) => s.toggleBlockCollapsed);
  const { title, html, height } = htmlPreview;
  const wrappedHtml = injectApi(html);

  useEffect(() => {
    function handleMessage(e: MessageEvent) {
      if (e.data?.source === "zspace-html-preview" && e.data?.action === "fillInput") {
        window.dispatchEvent(new CustomEvent("zspace:fillInput", { detail: e.data.text }));
      }
    }
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  return (
    <div className="border border-gray-200 border-l-[3px] border-l-[#722ed1] rounded-lg bg-white text-[13px]">
      <div
        onClick={() => toggle(blockId)}
        className="flex items-center gap-1.5 px-3.5 py-2.5 cursor-pointer select-none bg-gray-50 hover:bg-gray-100 transition-colors rounded-t-lg"
      >
        {collapsed ? (
          <RightOutlined style={{ color: "#722ed1", fontSize: 12 }} />
        ) : (
          <DownOutlined style={{ color: "#722ed1", fontSize: 12 }} />
        )}
        <CodeOutlined className="text-sm" style={{ color: "#722ed1" }} />
        <span className="font-semibold text-gray-700 truncate flex-1 ml-0.5">
          {title || "HTML 预览"}
        </span>
        <span className="text-xs text-gray-400 whitespace-nowrap">
          {collapsed ? "点击渲染" : `${height || 400}px`}
        </span>
      </div>

      {!collapsed && (
        <div className="border-t border-gray-200">
          <iframe
            srcDoc={wrappedHtml}
            title={title}
            sandbox="allow-scripts allow-same-origin"
            width="100%"
            height={height || 400}
            className="border-0"
            style={{ display: "block" }}
          />
        </div>
      )}
    </div>
  );
});
