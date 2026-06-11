---
title: "C++ 스마트포인터"
date: 2026-06-12
slug: "cpp-smart-pointer"
description: "delete를 자동으로 해주는 똑똑한 포인터. unique_ptr(주인 한 명, 복사 금지, move로 이전)과 shared_ptr(여러 명 공유, 참조 카운트로 마지막에 반납)을 직접 돌려본 출력으로 정리."
categories:
  - "C++"
tags:
  - "스마트포인터"
modality:
  - "code"
canonical_topic: "smart-pointer"
context: "cpp"
level: "beginner"
---

## 이 글에서 이해할 것

스마트 포인터가 `delete`를 자동으로 해준다는 것, 그리고 두 종류 — 주인이 한 명인 `unique_ptr`과 여러 명이 나눠 갖는 `shared_ptr` — 의 차이.

## 읽기 전 최소 배경

`new`/`delete`로 힙에 메모리를 빌리고 반납하는 것, `p`는 주소이고 `*p`는 그 안의 값이라는 것을 안다고 가정한다. `delete`를 깜빡하면 메모리 누수가 난다는 것도.

## 내가 막혔던 점 / 틀린 가설

`unique_ptr`도 일반 변수처럼 `q = p`로 복사되는 줄 알았다. 그리고 `unique_ptr<int>`의 `<int>`를 벡터 같은 거라고 착각했다.

## 확인한 증거

먼저 기본. `new int` 대신 `make_unique`로 만들면 `delete`가 사라진다.

```cpp
#include <iostream>
#include <memory>      // 스마트 포인터는 여기 들어있어
using namespace std;

int main()
{
    unique_ptr<int> p = make_unique<int>();
    *p = 13;
    cout << *p << endl;   // 13
    // delete 없음. 알아서 반납됨
    return 0;
}
```

직접 돌린 출력: `13`. `delete`를 한 줄도 안 썼는데 누수 없이 끝났다.

다음, `unique_ptr`을 복사하려고 했더니 막혔다.

```cpp
unique_ptr<int> p = make_unique<int>();
*p = 23;
unique_ptr<int> q = p;   // ← 컴파일 에러!
```

복사가 **컴파일 단계에서 막힌다.** 그래서 `move`로 바꿨다.

```cpp
unique_ptr<int> p = make_unique<int>();
*p = 23;
unique_ptr<int> q = move(p);   // 소유권을 q로 '이사'
cout << *q << endl;   // 23
cout << *p << endl;   // ← Segmentation fault!
```

직접 돌린 출력: `*q`는 23, 그런데 `*p`에서 **Segmentation fault**가 났다. move로 소유권을 넘긴 뒤라 `p`는 빈손이 됐고, 빈손인 `p`로 값을 꺼내려니 갈 곳이 없어서 죽은 것이다.

이제 `shared_ptr`. 이건 복사가 된다.

```cpp
#include <iostream>
#include <memory>
using namespace std;

int main()
{
    shared_ptr<int> p = make_shared<int>();   // 괄호 () 빠뜨리면 에러
    *p = 12;
    cout << p.use_count() << endl;   // 1

    {
        shared_ptr<int> q = p;           // 복사 OK
        cout << p.use_count() << endl;   // 2
    }   // ← 여기서 q가 사라짐 (블록 끝)

    cout << p.use_count() << endl;   // 1
    return 0;
}
```

직접 돌린 출력: `1` → `2` → `1`. `q`가 복사로 들어오면 카운트가 2로 늘고, `q`가 블록 `}`를 벗어나 사라지면 다시 1로 줄었다.

## 그래서 이렇게 이해했다

스마트 포인터는 `delete`를 자동으로 해주는 똑똑한 포인터다. `new`/`delete`를 직접 쓸 때 제일 골치였던 게 깜빡하면 누수, 두 번 하면 에러였는데, 그걸 알아서 처리해준다.

`unique_ptr`은 **주인이 딱 한 명**이다. 그래서 복사 자체를 금지한다. 복사가 되면 둘이 같은 창고를 가리키다가 각자 반납해서 같은 걸 두 번 반납하는 에러가 나기 때문이다. 넘기고 싶으면 `move`로 소유권을 통째로 이사시키는데, 이사한 뒤엔 원본(`p`)이 빈손이 된다. 그래서 빈손인 `p`를 `*p`로 건드리면 Segfault가 났던 것이다.

`shared_ptr`은 **여러 명이 나눠 갖는다.** 창고에 "지금 몇 명이 들고 있나" 칠판(참조 카운트)이 붙어 있어서, 복사하면 +1, 한 명이 사라지면 -1, 칠판이 0이 되는 순간(마지막 사람이 나감) 창고가 자동 반납된다. `use_count()`로 그 칠판 숫자를 직접 볼 수 있다.

나만의 규칙: **혼자 쓰면 **`unique_ptr`**, 같이 쓰면 **`shared_ptr`**.** 기본은 unique를 쓰고, 여러 곳에서 같은 걸 공유해야 하는데 누가 마지막까지 쓸지 모를 때만 shared를 쓴다.

## 다른 예시에 적용해보기

`move(p)`와, 앞서 new/delete에서 본 `return a`는 둘 다 별표 없이 포인터(변수) 자체를 넘긴다는 점이 비슷하다. 하지만 결과가 결정적으로 다르다.

```cpp
// 일반 포인터: 주소를 복사 → 원본도 여전히 유효
int* a = new int;
return a;          // a도 살아있고, 받은 쪽도 같은 창고를 가리킴

// unique_ptr: 소유권을 이전 → 원본은 빈손
unique_ptr<int> q = move(p);   // 이 줄 뒤로 p는 빈손
```

일반 포인터는 주소를 복사하니 원본과 사본이 같은 창고를 가리켜서 "누가 delete할지" 모호했는데, `unique_ptr`은 move로만 넘어가니 주인이 항상 한 명인 게 보장된다.

## 아직 모르는 것

여러 스레드가 동시에 같은 값을 건드릴 때 생기는 문제(데이터 레이스)는 스마트 포인터와 별개의 주제다. 그리고 언리얼에는 `TSharedPtr` 같은 자체 버전과 GC가 있어서 raw `new`를 거의 안 쓰는데, 원리는 여기서 배운 참조 카운트와 같다.

## 확인 질문

`unique_ptr<int> p = make_unique<int>();` 한 뒤 `unique_ptr<int> q = move(p);`를 하면, 그 다음 줄에서 `*p`를 출력하면 어떻게 될까? 그 이유는?

## 추가 학습 (2026-06-12)

### 확인한 증거

참조 카운트가 "누구의 것"인지 확인하려고 복사를 여러 단계로 만들었다. 일부러 `c`를 `a`가 아니라 `b`에서 복사했다.

```cpp
shared_ptr<int> a = make_shared<int>(10);
shared_ptr<int> b = a;
shared_ptr<int> c = b;   // a가 아니라 b에서 복사
cout << a.use_count() << endl;
{
    shared_ptr<int> d = c;
    cout << b.use_count() << endl;
}
cout << c.use_count() << endl;
```

직접 돌린 출력: `3` → `4` → `3`. 누구한테서 복사했는지, 누구의 `use_count()`를 찍는지는 결과에 아무 영향이 없었다.

함수에 넘길 때도 카운트가 움직이는지 확인했다.

```cpp
void attack(shared_ptr<int> target) {
    cout << "함수 안: " << target.use_count() << endl;
}

int main() {
    shared_ptr<int> monster = make_shared<int>(50);
    cout << "호출 전: " << monster.use_count() << endl;
    attack(monster);
    cout << "호출 후: " << monster.use_count() << endl;
}
```

직접 돌린 출력: `1` → `2` → `1`. 매개변수 `target`은 `monster`의 복사본으로 태어나서(+1), 함수가 끝나는 순간 소멸했다(-1).

unique_ptr이 정확히 뭘 막는지도 다시 봤다. 1차 학습 때는 "복사가 막힌다"까지만 확인했는데, 이번엔 에러 메시지 원문을 읽었다.

```javascript
error: call to implicitly-deleted copy constructor of 'unique_ptr<int>'
note: copy constructor is implicitly deleted because 'unique_ptr<int>'
      has a user-declared move constructor
```

그리고 "값 수정도 막히나?"를 직접 시험했다.

```cpp
unique_ptr<int> u = make_unique<int>(5);
*u = 99;                  // (가) 통과 — 값 수정은 됨
unique_ptr<int> v = u;    // (나) 컴파일 에러 — 복사 생성자가 deleted
```

직접 돌려서 (나)만 에러가 나는 것을 확인했다.

### 그래서 이렇게 이해했다

참조 카운트는 `a`나 `b` 같은 특정 포인터의 소유물이 아니다. 가리켜지는 객체에 딸린 숫자라서, 그 객체를 가리키는 어떤 shared_ptr로 `use_count()`를 찍어도 같은 값이 나온다.

함수에 shared_ptr을 값으로 넘기면 매개변수가 복사본이라 호출되는 동안 카운트가 +1, 함수가 끝나면 -1로 돌아온다. 블록 `{ }`에서 본 것과 같은 원리다 — 복사본이 태어나면 +1, 죽으면 -1.

unique_ptr이 금지하는 건 값 접근이 아니라 소유권 복사다. `*u`로 값을 읽고 쓰는 건 자유고, 포인터를 복사해서 주인을 둘로 만드는 것만 막는다. 에러 메시지가 말하듯 컴파일러가 복사 생성자 자체를 지워놨기 때문이다.

처음에 "몬스터 10마리가 같은 포인터를 공유해서 최적화된다"고 생각했는데 틀렸다. 그러면 1번 몬스터의 HP를 깎을 때 10마리 전부 깎인다 — 사실상 몬스터가 1마리라는 뜻이다. 몬스터 10마리 = 객체 10개 = shared_ptr도 각각이다.

shared_ptr이 진짜 푸는 문제는 이거다: 몬스터 1마리를 타겟팅 시스템, 체력바, 스포너 목록이 같이 가리킬 때(카운트 3), raw 포인터라면 "누가 언제 delete하나"가 골치다. 한 곳이 지워버리면 나머지는 죽은 메모리를 가리킨다. shared_ptr이면 타겟팅이 먼저 손을 놓아도 카운트만 3→2로 줄 뿐이고, 마지막 사용자가 놓아서 카운트가 0이 되는 순간에만 자동 반납된다.

### 확인 질문 (추가)

`attack(shared_ptr<int> target)` 함수를 호출하는 동안 카운트가 +1 되는 이유는? 함수가 끝나면 왜 다시 줄어들까?
