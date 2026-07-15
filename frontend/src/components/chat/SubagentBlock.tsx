import { memo } from "react";
import { Spin } from "antd";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  RobotOutlined,
  CheckCircleOutlined,
  LoadingOutlined,
  DownOutlined,
  RightOutlined,
  ToolOutlined,
  BulbOutlined,
} from "@ant-design/icons";
import type { Block, SubagentStep } from "../../stores/chat-store";
import { useChatStore } from "../../stores/chat-store";

const CODE_FONT = '"SF Mono", "Monaco", "Cascadia Code", monospace';

function latestStepSummary(step: SubagentStep | undefined): string {
  if (!step) return "准备中…";
  switch (step.step_type) {
    case "text":
      return step.content?.trim().slice(0, 50) || "生成中…";
    case "thinking":
      return "思考中…";
    case "tool_start":
      return `调用工具: ${step.tool ?? ""}`;
    case "tool_result":
      return `${step.tool ?? ""} 完成`;
    case "error":
      return `出错: ${step.content?.slice(0, 50) ?? ""}`;
    default:
      return "处理中…";
  }
}

function StepItem({ step }: { step: SubagentStep }) {
  switch (step.step_type) {
    case "text":
      return (
        <div className="text-xs text-gray-600">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{step.content ?? ""}</ReactMarkdown>
        </div>
      );
    case "thinking":
      return (
        <div className="text-xs text-gray-400 italic whitespace-pre-wrap">
          <BulbOutlined className="mr-1" />
          {step.content || "…"}
        </div>
      );
    case "tool_start":
      return (
        <div className="text-xs text-blue-600">
          <ToolOutlined className="mr-1" />
          <span className="font-semibold">调用工具: {step.tool}</span>
          <pre className="mt-1 text-gray-500 whitespace-pre-wrap break-all" style={{ fontFamily: CODE_FONT }}>
            {JSON.stringify(step.args, null, 2)}
          </pre>
        </div>
      );
    case "tool_result":
      return (
        <div className="text-xs text-green-600">
          <CheckCircleOutlined className="mr-1" />
          <span className="font-semibold">{step.tool} 返回</span>
          <pre className="mt-1 text-gray-600 whitespace-pre-wrap break-all max-h-[200px] overflow-auto" style={{ fontFamily: CODE_FONT }}>
            {step.result}
          </pre>
        </div>
      );
    case "error":
      return (
        <div className="text-xs text-red-500">
          <span>❌ {step.content}</span>
        </div>
      );
    default:
      return null;
  }
}

function SubagentBlock({ block }: { block: Block }) {
  const toggle = useChatStore((s) => s.toggleBlockCollapsed);
  const { task, steps = [], result, done } = block;
  const latestStep = steps.length > 0 ? steps[steps.length - 1] : undefined;

  return (
    <div className="border border-purple-200 border-l-[3px] border-l-purple-500 rounded-lg bg-purple-50 text-[13px]">
      <div
        onClick={() => toggle(block.id)}
        className="flex items-center gap-1.5 px-3.5 py-2.5 cursor-pointer select-none"
      >
        {block.collapsed ? (
          <RightOutlined style={{ color: "#722ed1", fontSize: 12 }} />
        ) : (
          <DownOutlined style={{ color: "#722ed1", fontSize: 12 }} />
        )}
        <RobotOutlined className="text-sm" style={{ color: "#722ed1" }} />
        <span className="font-semibold text-gray-700 truncate flex-1">
          子 Agent：{(task || "").slice(0, 60) || "任务执行中"}
          {task && task.length > 60 ? "…" : ""}
        </span>
        {done ? (
          <CheckCircleOutlined className="text-green-500 text-sm" />
        ) : (
          <Spin indicator={<LoadingOutlined style={{ fontSize: 14 }} />} size="small" />
        )}
      </div>

      {block.collapsed && !done && latestStep && (
        <div className="px-3.5 pb-2 text-xs text-purple-600/70 truncate">
          {latestStepSummary(latestStep)}
        </div>
      )}

      {!block.collapsed && (
        <div className="border-t border-purple-100 px-3.5 py-2.5 flex flex-col gap-2 max-h-[500px] overflow-auto">
          {steps.map((step, index) => (
            <StepItem key={index} step={step} />
          ))}
          {done && result && (
            <>
              <div className="border-t border-purple-200 my-1" />
              <div className="text-xs text-gray-400 select-none">返回内容</div>
              <div className="text-xs text-gray-700">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{result}</ReactMarkdown>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default memo(SubagentBlock);
