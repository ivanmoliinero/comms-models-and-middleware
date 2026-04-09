import http from 'k6/http';
import { SharedArray } from 'k6/data';
import { check } from 'k6';
import { scenario } from 'k6/execution';

const data = new SharedArray('requests', function () {
  const file = open('/benchmark_data.txt');
  let reqs = [];
  let lines = file.split('\n');
  
  for (let i = 0; i < lines.length; i++) {
    let line = lines[i].trim();
    if (line.startsWith('BUY')) {
      let parts = line.split(/\s+/);
      // Formato: BUY client_id request_id
      if (parts.length >= 3) {
        reqs.push({ client_id: parts[1], req_id: parts[2] });
      }
    }
  }
  return reqs;
});

export const options = {
  scenarios: {
    exact_requests: {
      executor: 'shared-iterations',
      vus: 100,
      iterations: data.length,
      maxDuration: '10m',
    },
  },
};

export default function () {
  const item = data[scenario.iterationInTest];
  // Concatenamos para crear un tracking_id único (ej: user00001_00001)
  const ticketId = `${item.client_id}_${item.req_id}`;
  const url = `http://44.200.158.49/buy?ticket_id=${ticketId}`;
  
  const res = http.get(url);
  
  check(res, {
    'Success (200 OK)': (r) => r.status === 200,
    'Duplicate ID (409 Conflict)': (r) => r.status === 409,
    'Sold Out (410 Gone)': (r) => r.status === 410,
    'Gateway/DB Error (500+)': (r) => r.status >= 500,
  });
}
