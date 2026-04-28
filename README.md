# 경매 투자 분석기

한국 법원경매 투자 분석 도구

- 위험도 채점 (권리·명도)
- 통계 기반 예상 낙찰가
- 취득세·양도세 자동 계산
- 대출·손익 시뮬레이션

**앱 주소**: https://duruduck.github.io/auction-analyzer/

---

## 북마클릿 설치 (필수)

### 1단계: 아래 코드 전체 복사

```
javascript:(()=>{const text=document.body.innerText;if(!text.includes("감정가")||!text.includes("유찰")){alert("경매마당 물건 페이지에서 사용해주세요");return}function parsePrice(str){if(!str)return 0;str=str.replace(/\s|,/g,"");let t=0;const e=str.match(/(\d+)억/),m=str.match(/(\d+)만/);const w=str.match(/억.*?(\d+)원$/)||str.match(/만.*?(\d+)원$/)||(!e&&!m&&str.match(/^(\d+)원?$/));if(e)t+=parseInt(e[1])*100000000;if(m)t+=parseInt(m[1])*10000;if(w?.[1]&&parseInt(w[1])<10000)t+=parseInt(w[1]);if(t===0){const r=str.match(/(\d{5,})/);if(r)t=parseInt(r[1])}return t}const addrM=text.match(/서울[^\n]{5,60}호/)||text.match(/경기[^\n]{5,60}호/)||text.match(/인천[^\n]{5,60}호/)||text.match(/부산[^\n]{5,60}호/)||text.match(/대구[^\n]{5,60}호/);const address=addrM?addrM[0].trim().replace(/\s+/g," "):"";let propertyType="다세대";if(text.includes("아파트"))propertyType="아파트";else if(text.includes("오피스텔"))propertyType="오피스텔";else if(text.includes("상가"))propertyType="상가";else if(text.includes("토지"))propertyType="토지";else if(text.includes("빌라"))propertyType="빌라";const apm=text.match(/감정가\s*\n?\s*([\d,억만원]+)/);const appraisalPrice=apm?parsePrice(apm[1]):0;const minm=text.match(/최저가\s*\n?\s*([\d,억만원]+)/);const minimumBidPrice=minm?parsePrice(minm[1]):0;const fm=text.match(/유찰\s*(\d+)회/);const failedBidCount=fm?parseInt(fm[1]):0;const bldM=text.match(/건물\s*([\d.]+)㎡[^(]*\(([\d.]+)평\)/);const areaPy=bldM?parseFloat(bldM[2]):0;const areaSqm=bldM?parseFloat(bldM[1]):0;const floorM=text.match(/(\d+)층\d+호/)||text.match(/(\d+)층/);const floor=floorM?parseInt(floorM[1]):null;const hasElevator=text.includes("승강기")||text.includes("엘리베이터");const yearM=text.match(/(\d{4})년.*?준공/)||text.match(/사용승인.*?(\d{4})년/);const builtYear=yearM?parseInt(yearM[1]):null;const buildingAge=builtYear?new Date().getFullYear()-builtYear:null;const isReAuction=text.includes("재매각");const inheritedRights=text.includes("매수인이 인수")||text.includes("인수함");const hasLienClaim=text.includes("유치권");const hasLegalSurfaceRight=text.includes("법정지상권");const hasRentReg=text.includes("임차권등기")||text.includes("임차권설정");let occupantType="미상";if(text.includes("소유자")&&text.includes("점유"))occupantType="소유자";else if(text.includes("임차인"))occupantType="임차인";const um=text.match(/미납[관리비]*\s*([\d,억만원]+)/);const unpaidManagementFee=um?parsePrice(um[1]):0;const ZONES=["서울특별시","서울시","서울 ","경기 과천","과천시","경기 성남","성남시 분당","성남시 수정","경기 하남","하남시","경기 광명","광명시","세종특별자치시","세종시"];let isAdjusted=false;for(const z of ZONES){if(address.includes(z)){isAdjusted=true;break}}const data={address,propertyType,appraisalPrice,minimumBidPrice,failedBidCount,isReAuction,areaPy,areaSqm,floor,hasElevator,buildingAge,builtYear,inheritedRights,hasLienClaim,hasLegalSurfaceRight,hasRentReg,occupantType,unpaidManagementFee,isAdjusted};const encoded=btoa(JSON.stringify(data));window.open(`https://duruduck.github.io/auction-analyzer/?data=${encoded}`,"auction","width=1200,height=900")})();
```

### 2단계: 북마크 생성

**Chrome / Edge**
1. 북마크바 우클릭 → "북마크 추가"
2. 이름: `경매 분석기`
3. URL 자리에 위 코드 붙여넣기
4. 저장

**Firefox**
1. `Ctrl + D`
2. 이름: `경매 분석기`
3. 주소에 위 코드 붙여넣기

### 3단계: 사용

1. 경매마당(madangs.com) 물건 페이지 열기
2. 북마크바에서 `경매 분석기` 클릭
3. 새 창에 분석 결과 자동 표시

---

## GitHub Pages 활성화 방법

1. 이 저장소 → **Settings**
2. 왼쪽 메뉴 → **Pages**
3. Source: **Deploy from a branch**
4. Branch: **main** / **(root)**
5. **Save**

약 1~2분 후 https://duruduck.github.io/auction-analyzer/ 접속 가능

---

## 주의사항

- 세금 계산은 참고용입니다. 실제 세액은 세무사 확인 권장
- 낙찰가율 통계: 대법원 경매통계 / 지지옥션 2020~2024 집계 기준
- 조정대상지역 목록: 2025년 기준, 정책 변경 시 수동 업데이트 필요
