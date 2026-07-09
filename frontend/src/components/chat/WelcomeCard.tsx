import { useEffect, useState } from "react";
import { Card, Progress, Statistic, Spin, Typography } from "antd";
import {
  ThunderboltOutlined,
  DatabaseOutlined,
  HddOutlined,
  CheckCircleOutlined,
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
      <div style={{ display: "flex", justifyContent: "center", padding: 80 }}>
        <Spin />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, padding: 80, color: "#bbb" }}>
        <ThunderboltFilled style={{ fontSize: 48, opacity: 0.2 }} />
        <Text style={{ color: "#bbb", fontSize: 14 }}>无法获取存储信息，请检查后端服务</Text>
      </div>
    );
  }

  const totalBytes = pools.reduce((s, p) => s + p.total_size, 0);
  const usedBytes = pools.reduce((s, p) => s + p.usage_size, 0);
  const availBytes = pools.reduce((s, p) => s + p.free_size, 0);
  const usagePct = totalBytes > 0 ? Math.round((usedBytes / totalBytes) * 100) : 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, padding: "24px 0" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <ThunderboltOutlined style={{ fontSize: 22, color: "#1677ff" }} />
        <div>
          <Text strong style={{ fontSize: 18 }}>欢迎使用极同学</Text>
          <br />
          <Text style={{ fontSize: 13, color: "#999" }}>你的 NAS 智能管理助手，通过自然语言管理存储设备</Text>
        </div>
      </div>

      <Card style={{ borderRadius: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <DatabaseOutlined style={{ color: "#1677ff" }} />
            <Text strong>总存储概览</Text>
          </div>
          <Text style={{ fontSize: 12, color: "#999" }}>共 {pools.length} 个存储池</Text>
        </div>
        <Progress
          percent={usagePct}
          strokeColor={statusColor(usagePct)}
          size="small"
          style={{ marginBottom: 16 }}
        />
        <div style={{ display: "flex", gap: 24 }}>
          <Statistic title="总容量" value={formatBytes(totalBytes)} valueStyle={{ fontSize: 16 }} />
          <Statistic title="已用" value={formatBytes(usedBytes)} valueStyle={{ fontSize: 16, color: usagePct > 85 ? "#ff4d4f" : "#333" }} />
          <Statistic title="可用" value={formatBytes(availBytes)} valueStyle={{ fontSize: 16, color: "#52c41a" }} />
        </div>
      </Card>

      {pools.map((pool) => {
        const pct = pool.total_size > 0 ? Math.round((pool.usage_size / pool.total_size) * 100) : 0;
        return (
          <Card key={pool.id} size="small" style={{ borderRadius: 10 }} bodyStyle={{ padding: "12px 16px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <HddOutlined style={{ color: "#1677ff" }} />
                <div>
                  <Text strong>{pool.display_name || pool.name}</Text>
                  <Text style={{ fontSize: 12, color: "#999", marginLeft: 6 }}>{pool.name}</Text>
                </div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Text style={{ fontSize: 12, color: "#999" }}>{pool.safe_hdd_count} 块磁盘</Text>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: pool.status === "ok" ? "#52c41a" : "#ff4d4f", display: "inline-block" }} />
                <Text style={{ fontSize: 12, color: pool.status === "ok" ? "#52c41a" : "#ff4d4f" }}>{pool.status === "ok" ? "正常" : pool.status}</Text>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <Progress
                percent={pct}
                size="small"
                strokeColor={statusColor(pct)}
                style={{ flex: 1, marginBottom: 0 }}
              />
              <Text style={{ fontSize: 12, color: "#999", whiteSpace: "nowrap" }}>
                {formatBytes(pool.usage_size)} / {formatBytes(pool.total_size)}
              </Text>
            </div>
            {pool.disk_list && pool.disk_list.length > 0 && (
              <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
                {pool.disk_list.map((disk) => (
                  <Text key={disk.sn} style={{ fontSize: 11, color: "#999", background: "#f5f5f5", padding: "2px 8px", borderRadius: 4 }}>
                    {disk.model} · {disk.temp}°C
                  </Text>
                ))}
              </div>
            )}
          </Card>
        );
      })}

      <div style={{ background: "#f6ffed", border: "1px solid #b7eb8f", borderRadius: 10, padding: "12px 16px", fontSize: 13, color: "#333", lineHeight: 1.6 }}>
        你可以尝试问我：<br />
        「sata12 存储池还剩多少空间」「帮我搜索一下文件名包含『备份』的文件」「删除 downloads 目录下 30 天前的文件」
      </div>
    </div>
  );
}
