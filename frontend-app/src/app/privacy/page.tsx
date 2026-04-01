export default function PrivacyPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <h1 className="text-3xl font-black mb-8">개인정보처리방침</h1>
      <div className="bg-[#111827] rounded-xl border border-[#1e293b] p-8 space-y-6 text-[#94a3b8] text-sm leading-relaxed">

        <section>
          <h2 className="text-lg font-bold text-white mb-3">1. 수집하는 개인정보</h2>
          <p>본 서비스는 현재 회원가입 없이 이용 가능하며, 다음의 정보만 자동으로 수집됩니다:</p>
          <ul className="list-disc pl-5 space-y-1 mt-2">
            <li>접속 로그 (IP 주소, 접속 시간, 요청 URL)</li>
            <li>브라우저 및 기기 정보 (User-Agent)</li>
          </ul>
          <p className="mt-2">별도의 개인정보(이름, 이메일 등)는 수집하지 않습니다.</p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">2. 수집 목적</h2>
          <ul className="list-disc pl-5 space-y-1">
            <li>서비스 정상 운영 및 오류 진단</li>
            <li>서비스 이용 통계 분석</li>
            <li>부정 이용 방지</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">3. 보유 및 이용 기간</h2>
          <p>접속 로그는 수집일로부터 <strong className="text-white">3개월</strong> 보관 후 파기합니다.</p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">4. 제3자 제공</h2>
          <p>수집된 정보는 제3자에게 제공하지 않습니다. 단, 법령에 의한 요청이 있는 경우 예외로 합니다.</p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">5. 외부 서비스</h2>
          <p>본 서비스는 분석을 위해 다음 외부 API를 사용합니다:</p>
          <ul className="list-disc pl-5 space-y-1 mt-2">
            <li>OpenAI API — 이용자의 개인정보는 전송하지 않으며, 경기 데이터만 전송합니다.</li>
            <li>Anthropic API — 동일하게 경기 데이터만 전송합니다.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">6. 쿠키 사용</h2>
          <p>본 서비스는 분석 결과 캐싱을 위해 브라우저의 sessionStorage를 사용하며, 서버로 전송되지 않습니다. 별도의 추적 쿠키는 사용하지 않습니다.</p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">7. 이용자의 권리</h2>
          <p>이용자는 개인정보 보호법 제35조~제37조에 따라 자신의 개인정보에 대한 열람, 정정, 삭제, 처리정지를 요청할 수 있습니다.</p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">8. 개인정보 보호책임자</h2>
          <p>개인정보 관련 문의사항은 아래로 연락해 주세요.</p>
          <p className="mt-1 text-white">이메일: josechang5744@gmail.com</p>
        </section>

        <p className="text-xs text-[#475569] pt-4 border-t border-[#1e293b]">
          시행일: 2026년 4월 1일
        </p>
      </div>
    </div>
  );
}
