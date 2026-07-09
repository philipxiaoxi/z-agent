import { useEffect, useState } from "react";
import { Card, Progress, Statistic, Spin, Typography } from "antd";
import {
  ThunderboltOutlined,
  DatabaseOutlined,
  HddOutlined,
  ThunderboltFilled,
} from "@ant-design/icons";

const { Text } = Typography;

interface DiskInfo {
  sn: string;
  pos: number;
  temp: number;
  model: string;
  health: string;
  status: string;
}

interface PoolInfo {
  id: number;
  name: string;
  display_name?: string;
  status: string;
  total_size: number;
  free_size: number;
  usage_size: number;
  safe_hdd_count: number;
  protocol: string;
  pool_type: string;
  disk_list: DiskInfo[];
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return (bytes / Math.pow(1024, i)).toFixed(1) + " " + units[i];
}

function statusColor(pct: number): string {
  return pct > 85 ? "#ff4d4f" : pct > 60 ? "#faad14" : "#52c41a";
}

export default function WelcomeCard() {
  const [pools, setPools] = useState<PoolInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch("/api/pools/")
      .then((res) => res.json())
      .then((data) => {
        if (data.pools && data.pools.length > 0) {
          setPools(data.pools);
        } else {
          setError(true);
        }
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center p-20">
        <Spin />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-2 p-20 text-gray-300">
        <ThunderboltFilled className="text-[48px] opacity-20" />
        <Text className="text-gray-300 text-sm">无法获取存储信息，请检查后端服务</Text>
      </div>
    );
  }

  const totalBytes = pools.reduce((s, p) => s + p.total_size, 0);
  const usedBytes = pools.reduce((s, p) => s + p.usage_size, 0);
  const availBytes = pools.reduce((s, p) => s + p.free_size, 0);
  const usagePct = totalBytes > 0 ? Math.round((usedBytes / totalBytes) * 100) : 0;

  return (
    <div className="flex flex-col gap-4 py-6">
      <div className="flex items-center gap-2.5">
        <ThunderboltOutlined className="text-[22px] text-[#1677ff]" />
        <div>
          <Text strong className="text-lg">欢迎使用极同学</Text>
          <br />
          <Text className="text-[13px] text-gray-400">你的 NAS 智能管理助手，通过自然语言管理存储设备</Text>
        </div>
      </div>

      <Card className="rounded-xl">
        <div className="flex justify-between items-center mb-3">
          <div className="flex items-center gap-1.5">
            <DatabaseOutlined className="text-[#1677ff]" />
            <Text strong>总存储概览</Text>
          </div>
          <Text className="text-xs text-gray-400">共 {pools.length} 个存储池</Text>
        </div>
        <Progress
          percent={usagePct}
          strokeColor={statusColor(usagePct)}
          size="small"
          style={{ marginBottom: 16 }}
        />
        <div className="flex gap-6">
          <Statistic title="总容量" value={formatBytes(totalBytes)} valueStyle={{ fontSize: 16 }} />
          <Statistic title="已用" value={formatBytes(usedBytes)} valueStyle={{ fontSize: 16, color: usagePct > 85 ? "#ff4d4f" : "#333" }} />
          <Statistic title="可用" value={formatBytes(availBytes)} valueStyle={{ fontSize: 16, color: "#52c41a" }} />
        </div>
      </Card>

      {pools.map((pool) => {
        const pct = pool.total_size > 0 ? Math.round((pool.usage_size / pool.total_size) * 100) : 0;
        return (
          <Card key={pool.id} size="small" className="rounded-[10px]" bodyStyle={{ padding: "12px 16px" }}>
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-2">
                <HddOutlined className="text-[#1677ff]" />
                <div>
                  <Text strong>{pool.display_name || pool.name}</Text>
                  <Text className="text-xs text-gray-400 ml-1.5">{pool.name}</Text>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Text className="text-xs text-gray-400">{pool.safe_hdd_count} 块磁盘</Text>
                <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: pool.status === "ok" ? "#52c41a" : "#ff4d4f" }} />
                <Text className="text-xs" style={{ color: pool.status === "ok" ? "#52c41a" : "#ff4d4f" }}>{pool.status === "ok" ? "正常" : pool.status}</Text>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Progress
                percent={pct}
                size="small"
                strokeColor={statusColor(pct)}
                style={{ flex: 1, marginBottom: 0 }}
              />
              <Text className="text-xs text-gray-400 whitespace-nowrap">
                {formatBytes(pool.usage_size)} / {formatBytes(pool.total_size)}
              </Text>
            </div>
            {pool.disk_list && pool.disk_list.length > 0 && (
              <div className="flex gap-1.5 mt-2 flex-wrap">
                {pool.disk_list.map((disk) => (
                  <Text key={disk.sn} className="text-[11px] text-gray-400 bg-gray-50 px-2 py-0.5 rounded">
                    {disk.model} · {disk.temp}°C
                  </Text>
                ))}
              </div>
            )}
          </Card>
        );
      })}

      <div className="bg-green-50 border border-green-300 rounded-[10px] px-4 py-3 text-[13px] text-gray-700 leading-relaxed">
        你可以尝试问我：<br />
        「sata12 存储池还剩多少空间」「帮我搜索一下文件名包含『备份』的文件」「删除 downloads 目录下 30 天前的文件」
      </div>
    </div>
  );
}
