import http from 'k6/http';
import { SharedArray } from 'k6/data';
import { check, sleep } from 'k6';
import { scenario } from 'k6/execution';

const data = new SharedArray('requests', function () {
  const file = open('/benchmark_data.txt');
  let reqs = [];
  let lines = file.split('\n');
  
  for (let i = 0; i < lines.length; i++) {
    let line = lines[i].trim();
    if (line.startsWith('BUY')) {
      let parts = line.split(/\s+/);
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
      vus: 800,
      iterations: data.length,
      maxDuration: '10m',
    },
  },
};

export default function () {
  const item = data[scenario.iterationInTest];
  const ticketId = `${item.client_id}_${item.req_id}`;
  const url = `http://44.201.10.142/buy?ticket_id=${ticketId}`;
  
  let res;
  let retries = 0;
  const MAX_RETRIES = 3;

  // Real-world retry logic for infrastructure saturation
  while (retries < MAX_RETRIES) {
    // The 'tags' parameter fixes the k6 memory warning
    res = http.get(url, { tags: { name: 'BuyEndpoint' } });
    
    if (res.status >= 500) {
      retries++;
      sleep(0.5); // Backoff for 500ms to let the AWS network breathe
    } else {
      break; // Success (200) or Client Error (409/410) breaks the loop
    }
  }
  
  check(res, {
    'Success (200 OK)': (r) => r.status === 200,
    'Duplicate ID (409 Conflict)': (r) => r.status === 409,
    'Sold Out (410 Gone)': (r) => r.status === 410,
    'Gateway/DB Error (500+)': (r) => r.status >= 500,
  });
}
