import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

export const ALLOCATION_COLORS = ['#86a48a', '#8689aa', '#b3624b', '#d4d6bc', '#5f7d64', '#5f6280', '#8a4735'];

export function AllocationDonut({ data, height = 200 }) {
  if (!data?.length) {
    return <div className="empty-state">No open positions yet.</div>;
  }
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius={54} outerRadius={80} paddingAngle={2}>
          {data.map((entry, i) => (
            <Cell key={entry.name} fill={ALLOCATION_COLORS[i % ALLOCATION_COLORS.length]} stroke="none" />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
