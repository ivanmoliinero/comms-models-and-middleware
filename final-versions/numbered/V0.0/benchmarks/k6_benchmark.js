import http from 'k6/http';
import { SharedArray } from 'k6/data';
import { check } from 'k6';
import { scenario } from 'k6/execution';

// 1. Memory-Efficient File Parsing
const data = new SharedArray('requests', function () {
  const file = open('/benchmark_data.txt');
  let reqs = [];
  let lines = file.split('\n');
  
  for (let i = 0; i < lines.length; i++) {
    let line = lines[i].trim();
    if (line.startsWith('BUY')) {
      let parts = line.split(/\s+/);
      if (parts.length >= 3) {
        reqs.push({ client_id: parts[1], seat_id: parts[2] });
      }
    }
  }
  return reqs;
});

export const options = {
  scenarios: {
    exact_requests: {
      executor: 'shared-iterations',
      vus: 800,                 // concurrent network streams
      iterations: data.length,   // Exactly 60,000 round-trips
      maxDuration: '10m',        // Failsafe timeout (will exit early upon completion)
    },
  },
};

export default function () {
  const item = data[scenario.iterationInTest];
  const url = `http://44.215.107.90/buy?ticket_id=${item.client_id}&seat_id=${item.seat_id}`;
  
  // 2. Synchronous Blocking Execution
  // The VU will wait here until the Gateway returns the payload.
  const res = http.get(url);
  
  // 3. Explicit Response Verification
  // This proves the response was fully received and evaluated.
  check(res, {
    'Success (200 OK)': (r) => r.status === 200,
    'Duplicate ID (409 Conflict)': (r) => r.status === 409,
    'Sold Out (410 Gone)': (r) => r.status === 410,
    'Gateway/DB Error (500+)': (r) => r.status >= 500,
  });
}
